# Module 4: WebSocket Protocol (RFC 6455)

Once the HTTP Upgrade handshake completes successfully, the connection switches from standard HTTP text parsing to the binary framing layer defined in **RFC 6455**. 

Rather than sending raw text strings separated by newlines—which is inefficient and prone to boundary parsing errors—WebSockets encapsulate messages into structured, compact binary frames. This module details the RFC 6455 framing specification, maps data and control opcodes, explains the mathematics of client-to-server masking, and implements a manual binary frame decoder in Java.

---

## Learning Objectives
By the end of this module, you will be able to:
1. **Analyze the bit-level structure of a WebSocket frame**, identifying headers, lengths, masks, and payload boundaries.
2. **Apply the XOR masking algorithm** to encode and decode frame payloads.
3. **Orchestrate frame fragmentation** to transmit large data streams without causing buffer overflows.
4. **Distinguish between data frames and control frames**, implementing proper ping-pong heartbeats and close-connection handshake sequences.
5. **Implement a Java parser** to read, decode, and unmask raw socket frames directly from an input stream.

---

## 1. RFC 6455 Architecture Overview

The design goal of the RFC 6455 framing layer is to provide a minimalist, low-overhead transport abstraction on top of a TCP stream:
- **Low Overhead**: Minimizes packet headers. While HTTP headers consume kilobytes, a WebSocket frame adds as little as **2 bytes** of overhead to a message.
- **Message boundaries**: TCP is a continuous byte stream with no concept of message start or end. The WebSocket frame header explicitly declares the payload length, allowing the parser to know exactly where one message ends and the next begins.
- **Stateful Framing**: Allows multiplexing control operations (like pings, pongs, and connection closes) directly inline with application text or binary data frames.

---

## 2. The WebSocket Frame Structure (Bit-Level Breakdown)

Every WebSocket frame, whether sent by the client or the server, conforms to the following binary structure:

```text
  0                   1                   2                   3
  0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
 +-+-+-+-+-------+-+-------------+-------------------------------+
 |F|R|R|R| opcode|M|     payload |    Extended payload length    |
 |I|S|S|S|  (4)  |A|     len (7) |             (16/64)           |
 |N|V|V|V|       |S|             |   (if payload len==126/127)   |
 | |1|2|3|       |K|             |                               |
 +-+-+-+-+-------+-+-------------+ - - - - - - - - - - - - - - - +
 |     Extended payload length continued, if payload len == 127  |
 + - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - +
 |                               |Masking-key, if MASK set (4)   |
 +-------------------------------+-------------------------------+
 | Masking-key (continued)       |          Payload Data         |
 +-------------------------------- - - - - - - - - - - - - - - - +
 :                     Payload Data continued ...                :
 +---------------------------------------------------------------+
```

### Bit-Field Descriptions:

#### 1. FIN (1 bit - Byte 1, Bit 7)
- **1 (set)**: Indicates that this is the final frame of a message.
- **0 (clear)**: Indicates that more frames follow (fragmented message).

#### 2. RSV1, RSV2, RSV3 (1 bit each - Byte 1, Bits 4-6)
Reserved for future extensions. Must be `0` unless an extension (such as compression via RFC 7692) is negotiated during the handshake. If a server receives a frame with non-zero reserved bits without negotiated extensions, it must drop the connection immediately (Protocol Error).

#### 3. Opcode (4 bits - Byte 1, Bits 0-3)
Defines how the payload data must be interpreted.
- `0x0`: Continuation Frame (associated with fragmented messages).
- `0x1`: Text Frame (UTF-8 encoded string data).
- `0x2`: Binary Frame (raw byte data).
- `0x8`: Connection Close.
- `0x9`: Ping.
- `0xA`: Pong.

#### 4. MASK (1 bit - Byte 2, Bit 7)
Defines whether the payload is encoded using a masking key.
- **1 (set)**: A 4-byte masking key is present in the frame header. **All frames sent from client to server must have this bit set**.
- **0 (clear)**: No masking key is present. **All frames sent from server to client must have this bit clear**.

#### 5. Payload Length (7 bits - Byte 2, Bits 0-6)
Decodes the size of the payload:
- **0 – 125**: This is the actual payload length.
- **126**: The payload size is 126–65,535 bytes. The next **2 bytes (16 bits)** of the header represent the payload length.
- **127**: The payload size exceeds 65,535 bytes. The next **8 bytes (64 bits)** of the header represent the payload length.

```
If Payload Length <= 125:
[Byte 1: FIN/Opcode] [Byte 2: M/Len] [Masking Key (4B)] [Payload Data]

If Payload Length == 126:
[Byte 1: FIN/Opcode] [Byte 2: M/126] [Extended Len (2B)] [Masking Key (4B)] [Payload Data]

If Payload Length == 127:
[Byte 1: FIN/Opcode] [Byte 2: M/127] [Extended Len (8B)] [Masking Key (4B)] [Payload Data]
```

---

## 3. Byte-by-Byte Handshake and Message Transmissions Traces

To see exactly how the binary framing layer behaves, let us trace the raw hexadecimal bytes transmitted over the socket for common message scenarios.

### Scenario A: Client Sends Masked Text Message "Hi"
The text payload is `"Hi"` (ASCII characters `H` (0x48) and `i` (0x69)).
- **Message Characteristics**: Single frame (`FIN = 1`), type is text (`Opcode = 0x1`), masked (`MASK = 1`), payload length is 2 bytes.
- **Header Byte 1 (FIN + Opcode)**:
  $$\text{Byte 1} = \text{FIN (bit 7)} \mid \text{Opcode (bits 0-3)} = 0\text{x}80 \mid 0\text{x}01 = 0\text{x}81$$
- **Header Byte 2 (MASK + Length)**:
  $$\text{Byte 2} = \text{MASK (bit 7)} \mid \text{Length (bits 0-6)} = 0\text{x}80 \mid 0\text{x}02 = 0\text{x}82$$
- **Masking Key**: Let us generate a random 4-byte key: `[0x11, 0x22, 0x33, 0x44]`.
- **Payload Masking Calculation (XOR)**:
  - Byte 0: `'H'` (0x48) $\oplus$ 0x11 = 0x59 (`'Y'`)
  - Byte 1: `'i'` (0x69) $\oplus$ 0x22 = 0x4B (`'K'`)
- **Raw Byte Stream**:
  `[0x81, 0x82, 0x11, 0x22, 0x33, 0x44, 0x59, 0x4B]`

---

### Scenario B: Server Pushes Unmasked Text Message "Welcome"
The text payload is `"Welcome"` (7 bytes).
- **Message Characteristics**: Single frame (`FIN = 1`), type is text (`Opcode = 0x1`), unmasked (`MASK = 0`).
- **Header Byte 1 (FIN + Opcode)**:
  $$\text{Byte 1} = 0\text{x}80 \mid 0\text{x}01 = 0\text{x}81$$
- **Header Byte 2 (MASK + Length)**:
  $$\text{Byte 2} = 0\text{x}00 \mid 0\text{x}07 = 0\text{x}07$$
- **Payload Data**: Raw ASCII values: `[0x57, 0x65, 0x6C, 0x63, 0x6F, 0x6D, 0x65]`
- **Raw Byte Stream**:
  `[0x81, 0x07, 0x57, 0x65, 0x6C, 0x63, 0x6F, 0x6D, 0x65]`
- *Result*: No masking key bytes are inserted, and the payload is sent in plain text.

---

### Scenario C: Client Transmits 200-Byte Masked Text Frame
- **Message Characteristics**: Single frame (`FIN = 1`), type is text (`Opcode = 0x1`), masked (`MASK = 1`), payload size 200 bytes.
- **Header Byte 1 (FIN + Opcode)**:
  $$\text{Byte 1} = 0\text{x}80 \mid 0\text{x}01 = 0\text{x}81$$
- **Header Byte 2 (MASK + Length)**: Since 200 is greater than 125, the initial length indicator must be set to 126:
  $$\text{Byte 2} = 0\text{x}80 \mid 126 = 0\text{x}FE$$
- **Extended Length Segment**: The value 200 is written as a 2-byte (16-bit) unsigned integer:
  $$\text{Bytes 3-4} = 0\text{x}00C8$$
- **Masking Key**: Let us assume `[0xAA, 0xBB, 0xCC, 0xDD]` (4 bytes).
- **Raw Byte Stream Outline**:
  `[0x81, 0xFE, 0x00, 0xC8, 0xAA, 0xBB, 0xCC, 0xDD, ... (200 masked bytes)]`

---

## 4. The XOR Masking Algorithm

Client-to-server frames must be masked to protect intermediate networks from **cache-poisoning attacks**:
- If a browser sends an unmasked frame containing HTTP request headers inside the WebSocket payload, an intermediate proxy might misinterpret the payload bytes as a new HTTP request, caching malicious content.
- Masking scrambles the payload bytes on the wire using a random 4-byte key, preventing proxies from recognizing pattern strings.

### The Mathematics:
For each byte of the payload $D_i$, the unmasked byte $U_i$ is computed using the Bitwise **XOR ($\oplus$)** operator with the masking key array $M$:
$$U_i = D_i \oplus M_{i \pmod 4}$$

Since XOR is symmetric, the same logic is used to both mask and unmask the data:
$$D_i \oplus M_{i \pmod 4} \oplus M_{i \pmod 4} = D_i$$

### Java Masking Implementation:
```java
package com.example.realtime.protocol;

public class WebSocketMasker {

    /**
     * Applies XOR masking/unmasking in-place on a byte array.
     */
    public static void applyMask(byte[] payload, byte[] maskingKey) {
        if (maskingKey == null || maskingKey.length != 4) {
            throw new IllegalArgumentException("Masking key must be exactly 4 bytes.");
        }
        
        for (int i = 0; i < payload.length; i++) {
            // Apply symmetric XOR transformation
            payload[i] = (byte) (payload[i] ^ maskingKey[i % 4]);
        }
    }
}
```

---

## 5. Frame Fragmentation

When sending large payloads (e.g. a 5 MB image), locking up the connection to send one giant frame would block high-priority control frames (like pings or urgent text messages). To prevent this, WebSockets support **Fragmentation**:
- The sender splits the payload into multiple frames.
- **Initial Frame**: Sets `FIN = 0` and the corresponding data opcode (e.g. `0x1` for Text).
- **Continuation Frames**: Sets `FIN = 0` and `Opcode = 0x0` (Continuation).
- **Final Frame**: Sets `FIN = 1` and `Opcode = 0x0`.

```
Fragmented Message Flow (FIN/Opcode mapping)
Frame 1: [FIN = 0, Opcode = 0x1 (Text)]  ──► (First block of payload)
Frame 2: [FIN = 0, Opcode = 0x0 (Cont)]  ──► (Second block of payload)
Frame 3: [FIN = 1, Opcode = 0x0 (Cont)]  ──► (Final block of payload)
```

The receiver buffers the incoming payloads until it encounters a frame with `FIN = 1`. Only then does it reassemble the bytes and deliver the message to the application.

---

## 6. Control Frames & Heartbeats

Control frames are used for connection management and state transitions. They can be interleaved between fragmented data frames to minimize latency.
- **Rules**: Control frames must have a payload length $\le 125$ bytes and **cannot be fragmented** (`FIN = 1` is mandatory).

### 1. Ping and Pong (Heartbeats)
- **Ping (Opcode `0x9`)**: Sent by either party to check connection health.
- **Pong (Opcode `0xA`)**: When a node receives a Ping, it **must** return a Pong containing the exact payload bytes received in the Ping frame as soon as possible.
- **NAT Keep-alive**: Periodic ping-pong loops keep firewalls from closing idle connection maps.

### 2. Close Frame (Opcode `0x8`)
To terminate a connection cleanly:
1. The close initiator sends a Close frame (`0x8`). It can optionally include a 2-byte unsigned status code followed by a UTF-8 reason string.
2. The receiver receives the Close frame, stops sending data, and echoes a Close frame back.
3. The TCP socket is closed.

#### Key RFC 6455 Close Status Codes:
* **1000 (Normal Closure)**: The connection has successfully completed its purpose.
* **1001 (Going Away)**: The server is shutting down, or the user navigated away from the page.
* **1002 (Protocol Error)**: A node received a frame that violates the protocol rules (e.g. an unmasked client frame).
* **1007 (Invalid Frame Payload)**: The received payload could not be decoded (e.g., malformed UTF-8 bytes in a text frame).
* **1009 (Message Too Big)**: A frame exceeded the maximum payload limit configured on the server.
* **1011 (Internal Error)**: The server encountered an unexpected runtime exception processing the request.

---

## 7. Extensions & Compression

RFC 6455 allows defining extensions to modify the framing layer behavior. The most common is **Per-Message Deflate (RFC 7692)**:
- During the handshake, the client sends `Sec-WebSocket-Extensions: permessage-deflate`.
- If the server supports it, it returns the extension header, enabling DEFLATE compression.
- **RSV1 Bit**: When compression is active, frames compress their payload, and set the **`RSV1` bit to 1** to instruct the receiver to pass the payload through a decompressor (Inflater) before parsing the frame content. This saves network bandwidth on repetitive JSON text feeds.
- **JVM Memory Impact**: Supporting `permessage-deflate` on a server with 100,000 active connections can exhaust the heap. Each session requires allocating an active `Deflater` and `Inflater` object, which retain native memory dictionaries (up to 32 KiB each). Sizing memory buffers and disabling compression for small payloads is a production best practice.

---

## 8. Hands-On Lab: Manual Frame Decoding

In this lab, you will implement a robust binary frame parser in Java. The parser will take a raw byte array representing a client-to-server text frame, read the header bits, resolve extended length boundaries (handling 16-bit and 64-bit offsets), locate the masking key, and apply the XOR algorithm to decode the hidden payload.

### The Lab Assignment:
Write a complete, compilable Java class `WebSocketFrameParser` that can decode:
1. A small masked text frame containing `"Hello"`.
2. A larger frame that uses the 16-bit extended length format.

```java
package com.example.realtime.protocol.lab;

import java.io.ByteArrayInputStream;
import java.io.DataInputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;

public class WebSocketFrameParser {

    /**
     * Parses and decodes a raw WebSocket frame from a byte array.
     */
    public static void parseFrame(byte[] frameBytes) throws IOException {
        System.out.println("\n--- Initializing WebSocket Frame Parser ---");
        
        DataInputStream dis = new DataInputStream(new ByteArrayInputStream(frameBytes));

        // 1. Read first byte: FIN, RSV1-3, and Opcode
        int b0 = dis.readUnsignedByte();
        boolean fin = (b0 & 0x80) != 0;
        int rsv1 = (b0 & 0x40) >> 6;
        int rsv2 = (b0 & 0x20) >> 5;
        int rsv3 = (b0 & 0x10) >> 4;
        int opcode = b0 & 0x0F;

        System.out.printf("Byte 0: 0x%02X%n", b0);
        System.out.printf("  [Bit 7] FIN    : %s%n", fin);
        System.out.printf("  [Bits 4-6] RSV : RSV1=%d, RSV2=%d, RSV3=%d%n", rsv1, rsv2, rsv3);
        System.out.printf("  [Bits 0-3] Op  : 0x%X (%s)%n", opcode, getOpcodeName(opcode));

        // 2. Read second byte: MASK and Payload Length
        int b1 = dis.readUnsignedByte();
        boolean masked = (b1 & 0x80) != 0;
        int initialLen = b1 & 0x7F;

        System.out.printf("Byte 1: 0x%02X%n", b1);
        System.out.printf("  [Bit 7] MASK   : %s (Mandatory for client: %s)%n", masked, masked);
        System.out.printf("  [Bits 0-6] Len : %d%n", initialLen);

        // 3. Resolve actual payload length
        long payloadLength = 0;
        if (initialLen <= 125) {
            payloadLength = initialLen;
        } else if (initialLen == 126) {
            // Next 16 bits define length
            payloadLength = dis.readUnsignedShort();
            System.out.printf("  Extended Length (16-bit): %d%n", payloadLength);
        } else if (initialLen == 127) {
            // Next 64 bits define length
            payloadLength = dis.readLong();
            System.out.printf("  Extended Length (64-bit): %d%n", payloadLength);
        }

        // 4. Extract 4-byte Masking Key
        byte[] maskingKey = new byte[4];
        if (masked) {
            dis.readFully(maskingKey);
            System.out.printf("  Masking Key    : [0x%02X, 0x%02X, 0x%02X, 0x%02X]%n",
                    maskingKey[0], maskingKey[1], maskingKey[2], maskingKey[3]);
        }

        // 5. Read payload data
        byte[] payloadBytes = new byte[(int) payloadLength];
        dis.readFully(payloadBytes);

        // 6. Apply symmetric XOR unmasking
        if (masked) {
            for (int i = 0; i < payloadBytes.length; i++) {
                payloadBytes[i] = (byte) (payloadBytes[i] ^ maskingKey[i % 4]);
            }
        }

        // 7. Interpret payload based on Opcode
        if (opcode == 0x1) {
            String text = new String(payloadBytes, StandardCharsets.UTF_8);
            System.out.printf("  Decoded Payload: \"%s\" (Length: %d)%n", text, payloadLength);
        } else {
            System.out.printf("  Binary Payload Length: %d bytes%n", payloadBytes.length);
        }
    }

    private static String getOpcodeName(int opcode) {
        return switch (opcode) {
            case 0x0 -> "Continuation Frame";
            case 0x1 -> "Text Frame";
            case 0x2 -> "Binary Frame";
            case 0x8 -> "Connection Close";
            case 0x9 -> "Ping Frame";
            case 0xA -> "Pong Frame";
            default -> "Unknown Opcode";
        };
    }

    public static void main(String[] args) throws IOException {
        // Test Frame 1: Masked client-to-server text frame containing "Hello"
        // Key: [0x37, 0xFA, 0x21, 0x3D]
        byte[] frame1 = {
            (byte) 0x81, // FIN=1, Opcode=1 (Text)
            (byte) 0x85, // MASK=1, Length=5
            (byte) 0x37, (byte) 0xFA, (byte) 0x21, (byte) 0x3D, // Masking Key
            (byte) 0x7F, (byte) 0x9F, (byte) 0x45, (byte) 0x51, (byte) 0x58  // Masked payload
        };
        parseFrame(frame1);

        // Test Frame 2: Masked client-to-server text frame containing a 130-character text string
        // Since 130 > 125, Byte 1 is 0xFE (Mask=1, Len=126). Bytes 2-3 are 0x00, 0x82 (Extended Len = 130).
        // Let's generate a mock frame array
        byte[] frame2 = new byte[2 + 2 + 4 + 130];
        frame2[0] = (byte) 0x81; // FIN=1, Opcode=1
        frame2[1] = (byte) 0xFE; // MASK=1, Len=126
        frame2[2] = 0x00;        // Extended Len High Byte
        frame2[3] = (byte) 0x82; // Extended Len Low Byte (130)
        // Key: [0x11, 0x11, 0x11, 0x11]
        frame2[4] = 0x11; frame2[5] = 0x11; frame2[6] = 0x11; frame2[7] = 0x11;
        // Fill payload with masked 'A' (0x41 ^ 0x11 = 0x50)
        for (int i = 8; i < frame2.length; i++) {
            frame2[i] = 0x50;
        }
        parseFrame(frame2);
    }
}
```

---

## 9. Common Mistakes & Debugging Scenarios

### Scenario A: Server Closes Connection with Code 1002 (Protocol Error)
* **The Problem**: A developer builds a custom Java WebSocket client. The connection handshakes fine, but the server immediately drops the link with status code `1002 (Protocol Error)` as soon as the client transmits its first message.
* **Why it happens**: According to the RFC 6455 specification, all frames sent from client to server **must** be masked using a random 4-byte key. The developer sent an unmasked frame (`MASK bit = 0` in Byte 1). The server rejects the connection to prevent proxy cache poisoning.
* **The Fix**: Update your client's frame generation logic to generate a random 4-byte masking key, set the MASK bit to 1, and XOR the payload before sending.

### Scenario B: StackOverflow or OutOfMemory during Message Reassembly
* **The Problem**: A WebSocket server crashes with an `OutOfMemoryError` or high memory footprint when processing large files uploaded by clients.
* **Why it happens**: The server reassembles fragmented frames (`Opcode = 0x0`) in memory, accumulating bytes in a list. If a client sends an infinite stream of continuation frames without setting `FIN = 1`, the server's reassembly buffer grows indefinitely until it exhausts the heap.
* **The Fix**: Configure a strict payload limit (e.g. 10 MB). If a client sends a message that exceeds this limit, abort the connection immediately with status code `1009 (Message Too Big)`.

---

## 10. Technical Interview Questions

### Question 1: WebSocket Framing Bit Manipulation
*How does a WebSocket frame represent payload lengths larger than 125 bytes? What is the maximum payload length a single frame can declare?*

**Answer**:
Byte 2 of the WebSocket frame header allocates 7 bits for the initial length representation:
1. If the length is **0 to 125 bytes**, it is written directly in those 7 bits.
2. If the length is **126 to 65,535 bytes**, the 7 bits are set to the value **126**, and the next **2 bytes (16 bits)** of the header represent the payload size as an unsigned integer.
3. If the length is **greater than 65,535 bytes**, the 7 bits are set to the value **127**, and the next **8 bytes (64 bits)** of the header represent the payload size.
The maximum payload length a single frame can declare is $2^{63}-1$ bytes (derived from the 64-bit unsigned field), though in practice servers limit payloads to smaller thresholds (e.g. 10–50 MB) to prevent resource exhaustion.

---

### Question 2: Why are Ping/Pong Frames Restricted to 125 Bytes?
*Why does RFC 6455 restrict control frames (Ping, Pong, Close) to a maximum payload size of 125 bytes?*

**Answer**:
Control frames are designed for connection management and must be processed immediately by network nodes. They are allowed to be interleaved between fragmented data frames (e.g. inserting a Ping frame between continuation frames of a large file upload). 

To prevent control frames from introducing high latency or requiring large allocation buffers themselves, the RFC restricts their size to $\le 125$ bytes. This ensures control frames can be parsed and responded to using small, stack-allocated buffers with near-zero overhead.

---

## Summary
- **RFC 6455** defines a compact binary framing layer that abstracts messages and control events with minimal header overhead.
- **The Frame Header** uses bitfields: `FIN` indicates finality, `Opcode` maps message types (Text, Binary, Ping, Pong, Close), and `MASK` defines whether data is XOR-encoded.
- **Masking** is mandatory for all client-to-server frames to protect intermediate proxies from cache poisoning.
- **Fragmentation** enables splitting large payloads into an initial frame, multiple continuation frames, and a final frame (`FIN=1`), preventing head-of-line blocking.
- **Control Frames** (Ping/Pong/Close) are small ($\le 125$ bytes) and non-fragmentable, enabling connection health checks and clean closures.
