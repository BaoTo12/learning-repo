# Module 05: Federated Single Sign-On (SSO) via SAML 2.0

Welcome back class. Today we analyze **Federated Single Sign-On (SSO) via SAML 2.0 (CS-527)**.

While OpenID Connect (OIDC) dominates modern mobile and single-page applications, many enterprise corporations and government entities rely on **Security Assertion Markup Language (SAML) 2.0** for identity federation. Developed as a XML-based standard, SAML uses signed XML assertions to communicate authentication states between Identity Providers and Service Providers. However, parsing XML introduces distinct security boundaries: XML engines can be vulnerable to file disclosure exploits if parsed without defensive parameters.

Today we study SAML 2.0 protocols, compare SAML against OIDC, dissect **XML External Entity (XXE) injection attacks**, and write a hardened Java XML parser that mitigates injection vulnerabilities.

---

## 1. Academic Lecture: XML Assertions & Parsing Vulnerabilities

### 1. SAML 2.0 Architecture: IdP vs. SP
*   **Identity Provider (IdP)**: The central authentication registry (e.g., Active Directory Federation Services, Okta). Authenticates users and generates signed SAML Assertions.
*   **Service Provider (SP)**: Your application. Trusting the IdP, it receives the SAML Assertion, verifies the signature, and logs the user in.
*   **SAML Assertion**: A highly structured XML document containing elements like `<saml:Subject>` (user identifier), `<saml:Conditions>` (validity timeframes), and `<saml:AttributeStatement>` (user groups and details).

### 2. XML Digital Signatures (DSIG)
SAML assertions are secured using **XML Signatures (DSIG)**. Unlike simple header-payload separation, XML signatures can sign specific sub-elements within the document. The signature block (`<ds:Signature>`) contains a `<ds:SignedInfo>` node outlining serialization rules (canonicalization) and the mathematical digest of the signed elements. Downstream verification must resolve XML canonicalization nuances to prevent signature forgery.

### 3. XML External Entity (XXE) Injection Mechanics
XML documents can define custom document type definitions (DTDs). These DTDs support "entities" (variables).
An **XML External Entity (XXE) attack** occurs when an XML parser processes input containing a reference to an external resource. An attacker can submit a malicious SAML assertion containing:
```xml
<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE root [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<samlp:Response ...>
  <saml:Assertion>
    <saml:Subject>
      <saml:NameID>&xxe;</saml:NameID>
    </saml:Subject>
  </saml:Assertion>
</samlp:Response>
```
If the parser has external entity resolution enabled, it will read `/etc/passwd` from the host filesystem, replace `&xxe;` with the file contents, and print it back to the user or transmit it to the attacker's server, leading to severe data leakage.

```mermaid
sequenceDiagram
    participant Attacker as Malicious Client
    participant SP as Service Provider (Java Application)
    participant Parser as XML Parser (DocumentBuilder)
    participant FS as Host Filesystem

    Attacker->>SP: POST SAML Assertion containing &xxe; entity
    SP->>Parser: Parse raw XML text
    alt External Entities Enabled (Vulnerable)
        Parser->>FS: Read local file: /etc/passwd
        FS->>Parser: Return contents
        Parser->>SP: Return document populated with file data
        SP->>Attacker: Return response reflecting data (Exploited!)
    else External Entities Disabled (Hardened)
        Parser->>Parser: Reject External Entity references
        Parser->>SP: Throw XMLParsingException
        SP->>Attacker: Return HTTP 400 Bad Request
    end
```

---

## 2. Theory vs. Production Trade-offs

When selecting an identity federation protocol, compare OIDC against SAML 2.0:

| Metric / Dimension | OpenID Connect (OIDC) | SAML 2.0 |
| :--- | :--- | :--- |
| **Data Format** | JSON (Lightweight key-value) | XML (Heavy markup schemas) |
| **Transport Protocol**| HTTP / REST (Resource endpoints) | HTTP POST / Redirect bindings |
| **Vulnerability Profile**| Moderate (Token theft, XSS) | High (XXE, Signature wrapping, DTD attacks) |
| **Mobile Integration** | Excellent (Native JSON parsing libraries) | Poor (Heavy XML parsing required) |
| **Enterprise Support** | Strong (Modern enterprise systems) | Monolithic (Legacy Active Directory / LDAP) |
| **Payload Size** | Small (Few hundred bytes) | Large (Often several kilobytes) |

---

## 3. How to Use: Hardened XML Parser in Java

Let us write a compile-grade Java 21 implementation of an XML parser that explicitly disables external general entities, parameter entities, and DTD processing.

### A. The Vulnerable Parsing Pattern (Anti-Pattern)

Avoid instantiating `DocumentBuilderFactory` without disabling feature flags. By default, standard JDK parsers have DTD resolution enabled, leaving your API open to file disclosure:

```java
package com.security.api.saml;

import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import org.w3c.dom.Document;
import java.io.ByteArrayInputStream;

public class NaiveXmlParser {
    // DANGER: Standard factory instantiation parses DTDs and external general entities by default.
    // Submitting a crafted XML document allows attackers to execute XXE injections.
    public Document parseSamlResponseUnsafe(String xmlString) throws Exception {
        DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
        factory.setNamespaceAware(true);
        DocumentBuilder builder = factory.newDocumentBuilder();
        return builder.parse(new ByteArrayInputStream(xmlString.getBytes())); // VULNERABLE
    }
}
```

### B. The Hardened Secure XML Parser (Production Pattern)

Here is the hardened pattern. We write a utility class that disables general entities, parameter entities, load-external DTDs, and enforce secure processing parameters.

```java
package com.security.api.saml;

import org.w3c.dom.Document;
import javax.xml.XMLConstants;
import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.parsers.ParserConfigurationException;
import java.io.ByteArrayInputStream;
import java.nio.charset.StandardCharsets;

public class SecureXmlParser {

    private final DocumentBuilderFactory factory;

    public SecureXmlParser() {
        this.factory = DocumentBuilderFactory.newInstance();
        this.factory.setNamespaceAware(true);
        
        try {
            // 1. Enforce secure-processing feature: sets limits on entity expansions
            this.factory.setFeature(XMLConstants.FEATURE_SECURE_PROCESSING, true);
            
            // 2. Completely disable inline DTD (Document Type Definitions)
            this.factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
            
            // 3. Disable External General Entities processing
            this.factory.setFeature("http://xml.org/sax/features/external-general-entities", false);
            
            // 4. Disable External Parameter Entities processing
            this.factory.setFeature("http://xml.org/sax/features/external-parameter-entities", false);
            
            // 5. Ensure external DTD load is disabled
            this.factory.setFeature("http://apache.org/xml/features/nonvalidating/load-external-dtd", false);
            
            // 6. Disable entity reference nodes expansion
            this.factory.setExpandEntityReferences(false);
            
        } catch (ParserConfigurationException e) {
            throw new IllegalStateException("Failed to configure secure XML parser features.", e);
        }
    }

    public Document parseXmlSafely(String rawXml) throws Exception {
        if (rawXml == null || rawXml.strip().isEmpty()) {
            throw new IllegalArgumentException("XML payload cannot be null or empty.");
        }
        
        try {
            DocumentBuilder builder = this.factory.newDocumentBuilder();
            // Optional: Register a custom null EntityResolver to block resolving attempts
            builder.setEntityResolver((publicId, systemId) -> {
                throw new ParserConfigurationException("External Entity Resolution Blocked: " + systemId);
            });
            
            return builder.parse(new ByteArrayInputStream(rawXml.getBytes(StandardCharsets.UTF_8)));
        } catch (Exception e) {
            throw new SecurityException("XML parsing blocked due to security configuration violations.", e);
        }
    }
}
```

---

## 4. Common Errors & Pitfalls

### Pitfall 1: Leaving namespace awareness disabled
Failing to invoke `factory.setNamespaceAware(true)`.
*   **Why it fails**: SAML signatures rely on XML Namespaces (e.g. `xmlns:saml`). If namespace awareness is disabled, signature validators cannot find elements properly, causing valid IdP requests to fail.
*   **Mitigation**: Always execute `factory.setNamespaceAware(true)` before configuring builder features.

### Pitfall 2: Signature Wrapping Attacks (XML Wrapping)
Validating that a signature exists in the document but failing to verify that it signs the *correct* parent node.
*   **Why it fails**: An attacker can copy a signed assertion from a valid user response and paste it into a new XML envelope. They then write their own unsigned assertion (with admin privileges) as a sibling node. If the SP verifier only checks that "a signature is valid" without checking *what* is signed, it grants admin access.
*   **Mitigation**: Ensure your verification code asserts that the validated `<ds:Signature>` element points directly to the root assertion ID tag, and confirm that there are no duplicate assertion tags in the document.

---

## 5. Socratic Review Questions

### Question 1
Why does setting the feature `http://apache.org/xml/features/disallow-doctype-decl` to `true` completely mitigate XXE attacks?

#### Answer
XXE attacks rely on defining external entities inside a custom `DOCTYPE` declaration (e.g., `<!DOCTYPE root [...]>`). Setting this feature to `true` instructs the parser to throw a configuration parsing error immediately if it encounters any `<!DOCTYPE>` tag in the document. This stops DTD processing before any entities can be declared or resolved.

### Question 2
What is the purpose of XML canonicalization (C14N) during signature verification, and why is it necessary?

#### Answer
XML documents can represent the exact same logical data using different string representations (e.g. different spacing, attributes order, or linebreaks). If a client changes an attribute position, a simple character-by-character string hash validation fails. Canonicalization defines strict transformation rules to convert XML into a standardized format, ensuring signatures validate regardless of formatting differences.

---

## 6. Hands-on Challenge: Secure XML Parser Validation

### The Challenge
In this challenge, you will implement security checks inside a JUnit 5 test suite to verify that your secure XML parser blocks malicious DTD payloads.
Your task:
1. Complete the implementation of the `TestXmlParserSecurity` class.
2. Assert that parsing a standard XML file passes (returns a non-null document).
3. Assert that parsing an XML string containing a `DOCTYPE` declaration raises a `SecurityException`.

Complete the implementation below:

```java
package com.security.api;

import com.security.api.saml.SecureXmlParser;
import org.junit.jupiter.api.Test;
import org.w3c.dom.Document;
import static org.junit.jupiter.api.Assertions.*;

public class TestXmlParserSecurity {

    @Test
    public void testValidXmlParsesSuccessfully() throws Exception {
        SecureXmlParser parser = new SecureXmlParser();
        String safeXml = "<saml:Response xmlns:saml=\"urn:oasis:names:tc:SAML:2.0:assertion\"><saml:ID>123</saml:ID></saml:Response>";
        
        Document doc = parser.parseXmlSafely(safeXml);
        assertNotNull(doc);
        assertEquals("123", doc.getElementsByTagName("saml:ID").item(0).getTextContent());
    }

    @Test
    public void testXmlWithDoctypeDeclIsRejected() {
        SecureXmlParser parser = new SecureXmlParser();
        
        // TODO: Construct a malicious XML string containing a DOCTYPE declaration:
        // "<!DOCTYPE root [<!ENTITY xxe SYSTEM \"file:///etc/passwd\">]><root>&xxe;</root>"
        // Assert that calling parser.parseXmlSafely(maliciousXml) throws a SecurityException.
    }
}
```

Write the test assertions. Save the completed file and verify that the security checks pass under `modules/05-saml-sso-federation.md`.
