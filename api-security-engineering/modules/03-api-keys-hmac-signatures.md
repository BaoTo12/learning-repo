# Module 03: Request Integrity & HMAC signatures

Welcome back class. Today we analyze **Request Integrity & HMAC Signatures (CS-527)**.

While stateless JWTs protect user sessions, machine-to-machine integrations (such as webhooks or background microservice calls) require a different authentication model. Storing static credentials inside background workers is risky: if a static token is intercepted, the attacker can replay it indefinitely. To secure high-stakes server-to-server integrations, we must verify both the identity of the client and the integrity of the request payload itself.

Today we study **HMAC Request Signing** (similar to AWS Signature Version 4), explore how to prevent replay attacks, and write a custom **Jakarta Servlet Filter** in Java 21 to validate request signatures in constant time.

---

## 1. Academic Lecture: Request Signatures vs. Static Tokens

### 1. Static API Keys vs. Cryptographic Request Signing
*   **Static API Keys**: The client includes a persistent string token in the request header (e.g. `X-API-Key: key_value`). This secret is sent across the network on every request, exposing it to sniffing or proxy log exposure. If stolen, the attacker can duplicate the header and access resources.
*   **HMAC Request Signing**: The client and server share a secret key, but this key is **never** transmitted in the request. Instead, for each request, the client compiles the request data (HTTP method, URI, timestamp, and body bytes) and computes a **Hash-Based Message Authentication Code (HMAC)** using the shared secret. The client transmits the signature, the client ID, and the timestamp. The server recalculates the signature using its copy of the secret and verifies a match.

### 2. Hash-Based Message Authentication Code (HMAC) Math
An HMAC uses a cryptographic hash function (e.g., SHA-256) combined with a secret cryptographic key:

$$\text{HMAC}(K, m) = \text{H}((K' \oplus \text{opad}) \parallel \text{H}((K' \oplus \text{ipad}) \parallel m))$$

Where $K$ is the secret key, $m$ is the request message string, $\text{opad}$ and $\text{ipad}$ are constant padding bytes, and $\parallel$ represents concatenation. If an attacker modifies even a single character in the request body $m$, the signature recalculation fails.

### 3. Replay Attacks and Nonces
If an attacker intercepts a signed request payload, they cannot modify the data, but they could resend the exact same signed packet to the server (e.g. duplicating a transaction). We block this using two checks:
*   **Timestamp Verification**: The client must include a timestamp header. The server rejects any request with a timestamp older than a short window (e.g., 5 minutes).
*   **Nonces (Number Used Once)**: The client appends a unique random string (nonce) to each request. The server saves used nonces in a fast cache (e.g., Redis) and rejects any request containing an already-used nonce.

```text
[Client App]
   ├── Compiles: Method + URI + Timestamp + Body
   ├── Signs using Shared Secret ──> Generates HMAC
   └── Transmits: Request + HMAC + Timestamp + ClientId
                                      │
                                      ▼
[Servlet Filter / API Gateway] ◀──────┘
   ├── Checks: Is current_time - Timestamp < 300 seconds?
   ├── Loads: Client Secret from Database
   ├── Recalculates: HMAC locally
   └── Verifies: Constant-Time Hash Equality ──> Pass to controller
```

---

## 2. Theory vs. Production Trade-offs

When securing server-to-server APIs, compare static keys against signed payloads:

| Dimension / Metric | Static API Keys | JWT Bearer Tokens | HMAC Request Signatures |
| :--- | :--- | :--- | :--- |
| **Integrity Protection**| None (Body can be modified) | None (Payload can be modified)| Excellent (Any body change invalidates hash) |
| **Sniffing Resilience** | Poor (Secret is sent on wire) | Moderate (JWT is sent on wire) | Excellent (Secret is never sent on wire) |
| **Replay Protection** | Poor (Key can be replayed) | Moderate (Valid until JWT exp) | Excellent (Blocked by nonce/timestamp) |
| **Implementation** | Very Simple (Header match) | Moderate (JWKS/Signature check)| Complex (Sign client + Verify filter) |
| **Compute Overhead** | Negligible (String check) | Moderate (Asymmetric math) | Low (Symmetric hashing math) |

---

## 3. How to Use: HMAC Verification Filter in Java

Let us write a compile-grade Java 21 implementation of a Jakarta Filter that intercept requests, checks timestamp bounds, and validates HMAC signatures using constant-time check operations.

### A. The Brittle String Comparison Pattern (Anti-Pattern)

Avoid comparing signatures using standard Java string equality, and avoid skipping timestamp validations:

```java
package com.security.api.filter;

import jakarta.servlet.http.HttpServletRequest;

public class NaiveHmacValidator {
    // DANGER: Using direct string comparison '==' or '.equals()' creates a timing attack vulnerability.
    // JVM execution returns immediately upon finding a mismatch, allowing attackers to guess the hash
    // character-by-character by measuring server response times.
    // Furthermore, skipping timestamp checks leaves endpoints open to replay attacks.
    public boolean validateSignatureUnsafe(HttpServletRequest request, String secret, String incomingSig) throws Exception {
        String computedSig = computeHmac(request, secret);
        return computedSig.equals(incomingSig); // VULNERABLE
    }

    private String computeHmac(HttpServletRequest request, String secret) {
        return "hash_value";
    }
}
```

### B. The Hardened HMAC Verification Filter (Production Pattern)

Here is the hardened pattern. We write a custom filter class that extracts request metadata, checks timestamp freshness limits, and performs constant-time cryptographic hash verification.

```java
package com.security.api.filter;

import jakarta.servlet.Filter;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.ServletRequest;
import jakarta.servlet.ServletResponse;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Instant;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

public class HmacValidationFilter implements Filter {

    private final String hmacAlgorithm = "HmacSHA256";
    private final long clockSkewLimitSeconds = 300; // 5 minutes window
    private final String clientSecret = "secure_shared_secret_value_12345"; // Mock DB secret

    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain)
            throws IOException, ServletException {
        
        HttpServletRequest httpRequest = (HttpServletRequest) request;
        HttpServletResponse httpResponse = (HttpServletResponse) response;

        String incomingSignature = httpRequest.getHeader("X-Signature");
        String timestampHeader = httpRequest.getHeader("X-Timestamp");
        String clientId = httpRequest.getHeader("X-Client-Id");

        // 1. Verify headers presence
        if (incomingSignature == null || timestampHeader == null || clientId == null) {
            httpResponse.sendError(HttpServletResponse.SC_UNAUTHORIZED, "Missing authentication headers.");
            return;
        }

        try {
            // 2. Validate timestamp freshness to prevent Replay Attacks
            long requestTimestamp = Long.parseLong(timestampHeader);
            long currentTimestamp = Instant.now().getEpochSecond();
            if (Math.abs(currentTimestamp - requestTimestamp) > clockSkewLimitSeconds) {
                httpResponse.sendError(HttpServletResponse.SC_UNAUTHORIZED, "Request timestamp expired (Replay Attempt).");
                return;
            }

            // 3. Reconstruct payload to compute target signature
            // Combine Method, Request URI, and the Timestamp
            String payloadToSign = httpRequest.getMethod() + "\n" +
                                   httpRequest.getRequestURI() + "\n" +
                                   timestampHeader;

            // 4. Compute expected local HMAC signature
            String expectedSignature = calculateHmac(payloadToSign, clientSecret);

            // 5. Compare using constant-time check to prevent Timing Attacks
            if (!constantTimeAreEqual(incomingSignature, expectedSignature)) {
                httpResponse.sendError(HttpServletResponse.SC_UNAUTHORIZED, "Invalid request signature.");
                return;
            }

            // Signature passes, proceed in filter chain
            chain.doFilter(request, response);

        } catch (NumberFormatException e) {
            httpResponse.sendError(HttpServletResponse.SC_BAD_REQUEST, "Malformed timestamp header.");
        } catch (Exception e) {
            httpResponse.sendError(HttpServletResponse.SC_INTERNAL_SERVER_ERROR, "Signature computation failure.");
        }
    }

    private String calculateHmac(String data, String secret) throws Exception {
        SecretKeySpec secretKey = new SecretKeySpec(secret.getBytes(StandardCharsets.UTF_8), hmacAlgorithm);
        Mac mac = Mac.getInstance(hmacAlgorithm);
        mac.init(secretKey);
        byte[] rawHmac = mac.doFinal(data.getBytes(StandardCharsets.UTF_8));
        return bytesToHex(rawHmac);
    }

    private boolean constantTimeAreEqual(String a, String b) {
        byte[] aBytes = a.getBytes(StandardCharsets.UTF_8);
        byte[] bBytes = b.getBytes(StandardCharsets.UTF_8);
        // MessageDigest.isEqual executes constant-time array comparison
        return MessageDigest.isEqual(aBytes, bBytes);
    }

    private String bytesToHex(byte[] bytes) {
        StringBuilder hexString = new StringBuilder();
        for (byte b : bytes) {
            String hex = Integer.toHexString(0xff & b);
            if (hex.length() == 1) hexString.append('0');
            hexString.append(hex);
        }
        return hexString.toString();
    }
}
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Timing attacks on hash comparisons
Comparing hex signatures using standard `.equals()`.
*   **Why it fails**: Standard string checks return `false` on the first character difference. If an attacker inputs `a123...` and the expected signature starts with `b`, the server rejects it in 1ms. If the first character matches, it takes 1.1ms. The attacker can measure these microsecond variations to guess the signature byte-by-byte.
*   **Mitigation**: Always use `MessageDigest.isEqual()` which performs a bitwise comparison of the entire array regardless of where a mismatch occurs.

### Pitfall 2: Excluding request body from payload signatures
Signing only the URL and HTTP method parameters while neglecting to hash the request body.
*   **Why it fails**: An attacker can capture a signed GET/POST request headers payload, modify the body contents (e.g. changing the transaction amount or target email parameters), and forward it. The signature remains valid because the modified parameters were not in the signature payload scope.
*   **Mitigation**: Always include the request body bytes (often hashed first using SHA-256) inside the signature construction payload template.

---

## 5. Socratic Review Questions

### Question 1
How does a timing attack work, and why does comparing strings character-by-character expose the system to vulnerability?

#### Answer
A timing attack targets early-exit algorithms. A standard equality loop exits immediately upon finding a mismatch. By measuring response times over thousands of queries, an attacker can determine if their input matched the first character, second character, etc., because each match adds a tiny, measurable calculation delay. Constant-time checks verify every element in the array, rendering response times identical.

### Question 2
Why does HMAC signature verification require the server to store client secrets in plain text or reversible encryption format, rather than salted hashes like passwords?

#### Answer
To verify a password, the server takes the user's input, hashes it, and checks if it matches the stored hash. The server never needs to know the raw password. For HMAC request signatures, the client sends a *hash signature* constructed using the secret key, not the secret key itself. The server must load the raw secret key from its database to calculate the expected HMAC locally. If the secret were hashed, the server could not reconstruct the signature.

---

## 6. Hands-on Challenge: HMAC Validator & Key Validator

### The Challenge
In this challenge, you will implement a signature validation class in Java.
Your task:
1. Complete the implementation of `verifySignature` in `HmacSignatureProcessor`.
2. Retrieve the matching client secret from `this.keyVault`.
3. Recalculate the expected signature based on `method`, `uri`, and `timestamp`.
4. Enforce a clock-skew check limit of 300 seconds.
5. Use constant-time comparison helper `MessageDigest.isEqual` to compare hashes.

Complete the implementation below:

```java
package com.security.api;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HashMap;
import java.util.Map;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

class HmacSignatureProcessor {
    private final Map<String, String> keyVault = new HashMap<>();
    private final String algo = "HmacSHA256";

    public HmacSignatureProcessor() {
        // Populating mock keys: ClientID -> SharedSecret
        keyVault.put("client_alpha", "secret_alpha_99");
        keyVault.put("client_beta", "secret_beta_88");
    }

    public boolean verifySignature(String clientId, String incomingSig, String timestamp, 
                                   String method, String uri, long currentEpochSecond) throws Exception {
        // TODO: Implement the validation logic:
        // 1. Retrieve the client secret from keyVault. If missing, return false.
        // 2. Validate timestamp freshness: check if Math.abs(currentEpochSecond - Long.parseLong(timestamp)) > 300.
        //    If it exceeds 300, return false.
        // 3. Format the signature payload: method + "\n" + uri + "\n" + timestamp.
        // 4. Calculate the expected HmacSHA256 signature using the shared secret.
        // 5. Convert calculated byte signature to a hexadecimal string.
        // 6. Compare the incoming signature string with the calculated expected signature
        //    using MessageDigest.isEqual(...) constant-time checks. Return the result.
        
        return false;
    }
}
```

Write the HMAC calculation and validator assertions. Save the completed file and verify that signature comparisons pass successfully under `modules/03-api-keys-hmac-signatures.md`.
