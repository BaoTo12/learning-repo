# Module 15: Authentication and Authorization

Securing a WebSocket gateway is a critical requirement for production systems. Unlike stateless REST APIs, WebSockets are long-lived, which introduces unique security challenges: standard browser WebSocket APIs do not support custom headers, URLs are frequently logged, and connections can remain active long after authentication tokens expire.

This module details how to implement secure authentication and authorization for WebSockets in Go. We will compare authentication strategies (JWT, Cookies, and Subprotocols), trace standard validation paths, implement handshake-level authentication middleware, propagate authenticated identities into the connection context, analyze security risks like Cross-Site WebSocket Hijacking (CSWSH), and build a complete authenticated upgrader system from scratch.

---

## Learning Objectives
By the end of this module, you will be able to:
1. **Analyze the limitations of browser WebSocket APIs** regarding custom headers.
2. **Evaluate the trade-offs** between JWT, Cookie, and Subprotocol authentication.
3. **Implement handshake-level validation middleware** in Go to reject unauthorized users early.
4. **Propagate authenticated identities** into the connection context using standard Go package structures.
5. **Mitigate security risks** like Cross-Site WebSocket Hijacking (CSWSH) and query parameter token leakage.
6. **Build a secure WebSocket gateway** featuring JWT token validation.

---

## 1. WebSocket Authentication Strategies

The standard browser JavaScript WebSocket API presents a challenge for authentication:
```javascript
// Browser JavaScript API
const socket = new WebSocket("ws://localhost:8080/ws");
// Note: You cannot pass custom headers (like Authorization: Bearer <token>) here!
```
Because the browser API does not support custom headers, developers must use alternative strategies to pass credentials:

---

### Strategy 1: JWT in Query Parameters
The token is appended to the connection URL as a query string:
`ws://localhost:8080/ws?token=eyJhbGciOi...`
- **Pros**: Easy to implement; works natively across all browsers.
- **Cons**: **Security Risk**. URLs are frequently logged by intermediate proxies, load balancers, and server application logs, exposing access tokens in plaintext files.

---

### Strategy 2: HTTP Cookie Authentication
If the user logged in using a standard web form, the browser stores a session identifier in a cookie. When initiating the WebSocket handshake, **the browser automatically appends the cookies** to the HTTP request headers.
- **Pros**: Secure and managed by the browser natively; credentials are not exposed in URL logs.
- **Cons**: Exposes the application to **Cross-Site WebSocket Hijacking (CSWSH)** if the server does not verify the `Origin` header.

---

### Strategy 3: Subprotocols Negotiation
The client passes the token as a subprotocol string:
`const socket = new WebSocket(url, ["access_token", "jwt_token_here"]);`
- **Pros**: Tokens are sent in headers (`Sec-WebSocket-Protocol`), preventing exposure in URL logs.
- **Cons**: Subprotocol strings must conform to header standards, and the server must handle the protocol matching.

---

## 2. Handshake-Level Authentication

**The Golden Rule**: **Always authenticate the client before upgrading the connection**.

```text
Unsecured Path:
Client ──► Upgrade to WebSocket ──► Socket Hijacked ──► Read Loop ──► Authenticate Token (Wasted Resources)

Secured Path:
Client ──► HTTP Middleware ──► Token Validated ──► Upgrade to WebSocket (Secure & Efficient)
```

Calling `Upgrade()` hijacks the TCP socket and allocates read/write buffers. 

If authentication is performed *after* the upgrade (e.g., waiting for the client to send a token inside the first data frame):
- Unauthenticated clients can open connections, consume socket buffers, and exhaust server file descriptors.
- This leaves the server vulnerable to resource exhaustion attacks.

Validating credentials at the HTTP handshake level allows the server to reject unauthorized requests early, returning standard HTTP errors (`401 Unauthorized` or `403 Forbidden`) without allocating socket resources.

---

## 3. Identity Propagation & Connection Context

Once authenticated in the middleware, the client's identity (User ID, role, or permissions) must be passed to the WebSocket upgrade handler.

In Go, this is done by modifying the request's context (`r.Context()`):
1. The authentication middleware validates the token.
2. It wraps the identity in a context value.
3. It passes the request to the next handler:
   ```go
   ctx := context.WithValue(r.Context(), userContextKey, claims)
   next.ServeHTTP(w, r.WithContext(ctx))
   ```
4. The upgrade handler retrieves the claims and associates them with the `Client` session:
   ```go
   claims := r.Context().Value(userContextKey).(*Claims)
   ```

This preserves the separation of concerns: the authentication middleware handles security, and the WebSocket handler focuses on routing frames.

---

## 4. WebSocket Security Risks

### 1. Cross-Site WebSocket Hijacking (CSWSH)
- If your application uses cookies for authentication, malicious sites can establish connections on behalf of logged-in users.
- **Mitigation**: Always validate the `Origin` header against an authorized domain whitelist in the upgrader config.

### 2. Token Leakage in Proxy Logs
- If JWT tokens are passed in query parameters, they are logged in plaintext by load balancers and gateways.
- **Mitigation**: Configure short token lifespans (e.g., 5 minutes) for WebSocket handshakes. Once upgraded, the connection remains active, but the leaked token expires quickly.

---

## 5. Exercises: Secure User Authentication

In this exercise, you will build a secure Go WebSocket gateway that implements JWT authentication middleware, extracts tokens from query parameters, propagates user identities into the context, and validates user roles before upgrading connections.

### Complete Go Server Implementation:

```go
package main

import (
	"context"
	"errors"
	"fmt"
	"log"
	"net/http"
	"strings"
	"time"
	"github.com/golang-jwt/jwt/v5"
	"github.com/gorilla/websocket"
)

var jwtKey = []byte("my_secret_signing_key_change_me")

type Claims struct {
	UserID string `json:"user_id"`
	Role   string `json:"role"` // "admin" or "user"
	jwt.RegisteredClaims
}

type contextKey string
const userContextKey contextKey = "user_claims"

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool {
		// Enforce origin validation to prevent CSWSH attacks
		return r.Header.Get("Origin") == "http://localhost:8080" || r.Header.Get("Origin") == ""
	},
}

// GenerateToken Helper for testing
func GenerateToken(userID string, role string) (string, error) {
	expirationTime := time.Now().Add(5 * time.Minute) // Short lifespan
	claims := &Claims{
		UserID: userID,
		Role:   role,
		RegisteredClaims: jwt.RegisteredClaims{
			ExpiresAt: jwt.NewNumericDate(expirationTime),
		},
	}
	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	return token.SignedString(jwtKey)
}

// 1. Handshake Authentication Middleware
func authenticateWS(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Extract token from query parameters
		tokenStr := r.URL.Query().Get("token")
		if tokenStr == "" {
			log.Println("[Auth Middleware] Refused: Token missing")
			http.Error(w, "Unauthorized: Token missing", http.StatusUnauthorized)
			return
		}

		// Parse and validate the JWT token
		claims := &Claims{}
		token, err := jwt.ParseWithClaims(tokenStr, claims, func(token *jwt.Token) (interface{}, error) {
			return jwtKey, nil
		})

		if err != nil || !token.Valid {
			log.Printf("[Auth Middleware] Refused: Token invalid: %v\n", err)
			http.Error(w, "Unauthorized: Token invalid", http.StatusUnauthorized)
			return
		}

		// Propagate claims into the request context
		ctx := context.WithValue(r.Context(), userContextKey, claims)
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

// 2. Authenticated Upgrade Handler
func handleSecureUpgrade(w http.ResponseWriter, r *http.Request) {
	// Retrieve claims from context
	claims, ok := r.Context().Value(userContextKey).(*Claims)
	if !ok {
		http.Error(w, "Internal Error", http.StatusInternalServerError)
		return
	}

	// 3. Authorization Check: Restrict access based on user role
	if claims.Role != "admin" {
		log.Printf("[Authorization] Refused: User %s has insufficient permissions (Role: %s)\n", claims.UserID, claims.Role)
		http.Error(w, "Forbidden: Insufficient permissions", http.StatusForbidden)
		return
	}

	// Upgrade connection
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Println("Upgrade failed:", err)
		return
	}
	defer conn.Close()

	log.Printf("[Gateway] Secure session established for Administrator: %s\n", claims.UserID)

	// Simple Echo loop
	for {
		messageType, payload, err := conn.ReadMessage()
		if err != nil {
			break
		}
		if err := conn.WriteMessage(messageType, payload); err != nil {
			break
		}
	}
}

func main() {
	// Register secure WebSocket route with authentication middleware
	http.Handle("/ws", authenticateWS(http.HandlerFunc(handleSecureUpgrade)))

	// Helper route to generate tokens for testing
	http.HandleFunc("/token", func(w http.ResponseWriter, r *http.Request) {
		role := r.URL.Query().Get("role")
		if role == "" {
			role = "user"
		}
		token, _ := GenerateToken("user_alice", role)
		fmt.Fprintf(w, "Token: %s", token)
	})

	log.Println("[Secure Gateway] Running server on :8080...")
	http.ListenAndServe(":8080", nil)
}
```

---

### Line-by-Line Code Walkthrough:

- **Line 26**: `type Claims struct { ... }`
  Defines the JWT claims struct, including `UserID` and `Role` fields.
- **Line 47**: `func authenticateWS(...)`
  The authentication middleware handler. It intercepts requests before they reach the upgrade handler.
- **Line 50**: `tokenStr := r.URL.Query().Get("token")`
  Extracts the JWT token from the query parameters, as browser WebSocket APIs do not support custom headers.
- **Line 59**: `token, err := jwt.ParseWithClaims(...)`
  Parses the token string and validates the signature using the server's secret key.
- **Line 68**: `ctx := context.WithValue(r.Context(), userContextKey, claims)`
  Wraps the validated claims in a context value and propagates it to the next handler.
- **Line 76**: `claims, ok := r.Context().Value(userContextKey).(*Claims)`
  Retrieves the claims from the request context in the upgrade handler.
- **Line 83**: `if claims.Role != "admin" { ... }`
  Enforces role-based access control, rejecting non-admin users with `HTTP 403 Forbidden`.

---

## 6. Common Pitfalls & Troubleshooting

### 1. Token Expiration on Long-Lived Connections
- **The Problem**: WebSockets are long-lived, and a connection can remain active long after the handshake-level authentication token has expired.
- **The Solution**: 
  - For high-security systems, enforce connection lifespans (e.g. 1 hour) and force clients to reconnect to validate their credentials.
  - Alternatively, implement an application-level message to re-authenticate or refresh tokens over the socket channel.

### 2. CSWSH via Cookies
- **The Problem**: Using cookies for authentication without origin checks exposes the application to CSWSH attacks.
- **The Solution**: Always validate the `Origin` header against an authorized domain whitelist in the upgrader config.

---

## 7. Technical Interview Questions

### Question 1: Browser WebSocket Header Limits
*Why can't browser WebSocket clients pass standard `Authorization: Bearer <token>` headers? How do you work around this?*

**Answer**:
The standard browser JavaScript WebSocket API constructor does not support custom headers. 

To work around this, you must pass the token as a query parameter (`?token=jwt`), use HTTP cookies, or negotiate credentials via subprotocols.

---

### Question 2: Handshake Validation Efficiency
*Why should authentication be performed during the handshake instead of inside the WebSocket read loop?*

**Answer**:
Performing authentication during the handshake allows the server to reject unauthorized connections early using standard HTTP error codes, preventing the allocation of socket buffers and thread resources for unauthorized clients.

---

### Question 3: Query Parameter Security
*What is the main security risk of passing authentication tokens in query parameters? How do you mitigate this?*

**Answer**:
URLs are frequently logged in plaintext by load balancers, gateways, and application servers. 

To mitigate this risk, configure short token lifespans (e.g. 5 minutes) for handshakes so that any leaked tokens expire quickly.

---

### Question 4: Identity Context Propagation
*How do you propagate client identity from authentication middleware to the upgrade handler in Go?*

**Answer**:
Use Go's request context:
1. The middleware validates the token.
2. It wraps the identity claims in `context.WithValue(r.Context(), key, claims)`.
3. It passes the request to the next handler, where the upgrade handler retrieves the claims from the context.

---

### Question 5: Cookie Auth CSWSH vulnerability
*Why are cookie-authenticated WebSockets vulnerable to Cross-Site WebSocket Hijacking (CSWSH) attacks?*

**Answer**:
Browsers automatically include cookies with cross-origin requests. 

If origin verification is disabled, a malicious site can establish a connection on behalf of a logged-in user, accessing sensitive data.

---

### Question 6: Token Re-Authentication
*How do you handle token expiration on connections that remain active for days?*

**Answer**:
Enforce connection lifespans (e.g. 1 hour) and force clients to reconnect, or implement application-level messages to re-authenticate or refresh tokens over the socket channel.

---

### Question 7: Subprotocols Token Authentication
*Explain how the `Sec-WebSocket-Protocol` header is used to pass tokens securely.*

**Answer**:
The client passes the token as a subprotocol string:
`new WebSocket(url, ["access_token", "token_value"])`
The browser includes the token in the `Sec-WebSocket-Protocol` header, avoiding token exposure in URL logs.

---

### Question 8: HTTP status 403 vs 401
*When should the authentication middleware return `HTTP 401 Unauthorized` versus `HTTP 403 Forbidden`?*

**Answer**:
- Return **`401 Unauthorized`** if the client's token is missing, invalid, or expired.
- Return **`403 Forbidden`** if the client is authenticated but has insufficient permissions (e.g. non-admin user trying to access admin routes).

---

### Question 9: Gorilla CheckOrigin logic
*What is the default behavior of Gorilla's `Upgrader` if `CheckOrigin` is nil?*

**Answer**:
It compares the domain in the client's `Origin` header to the domain in the server's `Host` header. 

If they do not match, the upgrader rejects the connection with `HTTP 403 Forbidden`.

---

### Question 10: context.Context Value Collisions
*Why should you use custom unexported types for context keys?*

**Answer**:
Using custom types for context keys prevents collisions with keys set by other packages.

---

## Summary
- **WebSocket Authentication** requires alternative strategies (JWT query parameters, Cookies, or Subprotocols) because browser APIs do not support custom headers.
- **Authenticate clients** at the handshake level before upgrading connections to protect server resources.
- **Propagate user identity** into the connection context using standard Go context values.
- **Mitigate CSWSH attacks** by verifying origin headers.
- **Keep token lifespans short** to prevent token leakage in URL logs.
- Protect shared client metadata from concurrent write access panics.
