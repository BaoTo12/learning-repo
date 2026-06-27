import os
import subprocess

base_path = r"c:\Users\Admin\Desktop\projects\learning-repo\practice\mtls-security"

files_dict = {
    # 1. pom.xml is already written, let's write configuration files
    "src/main/resources/application.yml": """
server:
  port: 8443
  ssl:
    enabled: true
    key-store: classpath:order-keystore.p12
    key-store-password: password
    key-store-type: PKCS12
    key-alias: order
    trust-store: classpath:order-truststore.p12
    trust-store-password: password
    trust-store-type: PKCS12
    client-auth: need
""",

    # 2. com.ftgo.order.config.HttpRedirectConfig
    "src/main/java/com/ftgo/order/config/HttpRedirectConfig.java": """package com.ftgo.order.config;

import org.apache.catalina.connector.Connector;
import org.apache.tomcat.util.descriptor.web.SecurityCollection;
import org.apache.tomcat.util.descriptor.web.SecurityConstraint;
import org.springframework.boot.web.embedded.tomcat.TomcatServletWebServerFactory;
import org.springframework.boot.web.servlet.server.ServletWebServerFactory;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class HttpRedirectConfig {

    @Bean
    public ServletWebServerFactory servletContainer() {
        TomcatServletWebServerFactory tomcat = new TomcatServletWebServerFactory() {
            @Override
            protected void postProcessContext(org.apache.catalina.Context context) {
                SecurityConstraint securityConstraint = new SecurityConstraint();
                securityConstraint.setUserConstraint("CONFIDENTIAL");
                SecurityCollection collection = new SecurityCollection();
                collection.addPattern("/*");
                securityConstraint.addCollection(collection);
                context.addConstraint(securityConstraint);
            }
        };
        tomcat.addAdditionalTomcatConnectors(createHttpConnector());
        return tomcat;
    }

    private Connector createHttpConnector() {
        Connector connector = new Connector(TomcatServletWebServerFactory.DEFAULT_PROTOCOL);
        connector.setScheme("http");
        connector.setPort(8081);
        connector.setSecure(false);
        connector.setRedirectPort(8443);
        return connector;
    }
}
""",

    # 3. com.ftgo.kitchen.config.FeignClientSSLConfig
    "src/main/java/com/ftgo/kitchen/config/FeignClientSSLConfig.java": """package com.ftgo.kitchen.config;

import feign.Client;
import org.apache.http.conn.ssl.NoopHostnameVerifier;
import org.apache.http.conn.ssl.SSLConnectionSocketFactory;
import org.apache.http.impl.client.CloseableHttpClient;
import org.apache.http.impl.client.HttpClients;
import org.apache.http.ssl.SSLContexts;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.io.ClassPathResource;

import javax.net.ssl.SSLContext;
import java.io.InputStream;
import java.security.KeyStore;

@Configuration
public class FeignClientSSLConfig {

    @Bean
    public Client feignClient() {
        try {
            KeyStore keyStore = KeyStore.getInstance("PKCS12");
            try (InputStream keyStoreStream = new ClassPathResource("kitchen-keystore.p12").getInputStream()) {
                keyStore.load(keyStoreStream, "password".toCharArray());
            }

            KeyStore trustStore = KeyStore.getInstance("PKCS12");
            try (InputStream trustStoreStream = new ClassPathResource("kitchen-truststore.p12").getInputStream()) {
                trustStore.load(trustStoreStream, "password".toCharArray());
            }

            SSLContext sslContext = SSLContexts.custom()
                    .loadKeyMaterial(keyStore, "password".toCharArray())
                    .loadTrustMaterial(trustStore, null)
                    .build();

            SSLConnectionSocketFactory socketFactory = new SSLConnectionSocketFactory(
                    sslContext,
                    NoopHostnameVerifier.INSTANCE
            );

            CloseableHttpClient httpClient = HttpClients.custom()
                    .setSSLSocketFactory(socketFactory)
                    .build();

            return new feign.httpclient.ApacheHttpClient(httpClient);

        } catch (Exception ex) {
            throw new IllegalStateException("Failed to configure secure mTLS Feign Client!", ex);
        }
    }
}
""",

    # 4. com.ftgo.kitchen.client.OrderFeignClient
    "src/main/java/com/ftgo/kitchen/client/OrderFeignClient.java": """package com.ftgo.kitchen.client;

import com.ftgo.kitchen.model.Order;
import com.ftgo.kitchen.config.FeignClientSSLConfig;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestMethod;

@FeignClient(
    name = "order-service",
    url = "https://localhost:8443",
    configuration = FeignClientSSLConfig.class
)
public interface OrderFeignClient {

    @RequestMapping(
        method = RequestMethod.GET,
        value = "/v1/orders/{orderId}",
        consumes = "application/json"
    )
    Order getOrder(@PathVariable("orderId") String orderId);
}
""",

    # 5. com.ftgo.kitchen.model.Order
    "src/main/java/com/ftgo/kitchen/model/Order.java": """package com.ftgo.kitchen.model;

public class Order {
    private String id;
    private String state;

    public Order() {}
    public Order(String id, String state) {
        this.id = id;
        this.state = state;
    }
    public String getId() { return id; }
    public void setId(String id) { this.id = id; }
    public String getState() { return state; }
    public void setState(String state) { this.state = state; }
}
""",

    # 6. com.ftgo.kitchen.config.WebClientMtlsConfig
    "src/main/java/com/ftgo/kitchen/config/WebClientMtlsConfig.java": """package com.ftgo.kitchen.config;

import io.netty.handler.ssl.SslContext;
import io.netty.handler.ssl.SslContextBuilder;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.io.ClassPathResource;
import org.springframework.http.client.reactive.ReactorClientHttpConnector;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.netty.http.client.HttpClient;

import javax.net.ssl.KeyManagerFactory;
import javax.net.ssl.TrustManagerFactory;
import java.io.InputStream;
import java.security.KeyStore;

@Configuration
public class WebClientMtlsConfig {

    @Bean
    public WebClient secureWebClient() {
        try {
            KeyStore keyStore = KeyStore.getInstance("PKCS12");
            try (InputStream ksStream = new ClassPathResource("kitchen-keystore.p12").getInputStream()) {
                keyStore.load(ksStream, "password".toCharArray());
            }
            KeyManagerFactory keyManagerFactory = KeyManagerFactory.getInstance(KeyManagerFactory.getDefaultAlgorithm());
            keyManagerFactory.init(keyStore, "password".toCharArray());

            KeyStore trustStore = KeyStore.getInstance("PKCS12");
            try (InputStream tsStream = new ClassPathResource("kitchen-truststore.p12").getInputStream()) {
                trustStore.load(tsStream, "password".toCharArray());
            }
            TrustManagerFactory trustManagerFactory = TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm());
            trustManagerFactory.init(trustStore);

            SslContext sslContext = SslContextBuilder.forClient()
                    .keyManager(keyManagerFactory)
                    .trustManager(trustManagerFactory)
                    .build();

            HttpClient httpClient = HttpClient.create()
                    .secure(sslContextSpec -> sslContextSpec.sslContext(sslContext));

            return WebClient.builder()
                    .clientConnector(new ReactorClientHttpConnector(httpClient))
                    .baseUrl("https://localhost:8443")
                    .build();

        } catch (Exception ex) {
            throw new IllegalStateException("Failed to build secure reactive WebClient mTLS context!", ex);
        }
    }
}
""",

    # 7. com.ftgo.kitchen.security.ReloadableX509TrustManager
    "src/main/java/com/ftgo/kitchen/security/ReloadableX509TrustManager.java": """package com.ftgo.kitchen.security;

import javax.net.ssl.X509ExtendedTrustManager;
import javax.net.ssl.TrustManagerFactory;
import java.io.File;
import java.io.FileInputStream;
import java.security.KeyStore;
import java.security.cert.CertificateException;
import java.security.cert.X509Certificate;
import java.net.Socket;
import javax.net.ssl.SSLEngine;

public class ReloadableX509TrustManager extends X509ExtendedTrustManager {

    private final String truststorePath;
    private final String password;
    private X509ExtendedTrustManager currentTrustManager;

    public ReloadableX509TrustManager(String truststorePath, String password) {
        this.truststorePath = truststorePath;
        this.password = password;
        reload();
    }

    public synchronized void reload() {
        try {
            KeyStore trustStore = KeyStore.getInstance("PKCS12");
            try (FileInputStream fis = new FileInputStream(new File(truststorePath))) {
                trustStore.load(fis, password.toCharArray());
            }

            TrustManagerFactory tmf = TrustManagerFactory.getInstance(TrustManagerFactory.getDefaultAlgorithm());
            tmf.init(trustStore);

            for (javax.net.ssl.TrustManager tm : tmf.getTrustManagers()) {
                if (tm instanceof X509ExtendedTrustManager) {
                    this.currentTrustManager = (X509ExtendedTrustManager) tm;
                    break;
                }
            }
        } catch (Exception e) {
            throw new IllegalStateException("Failed to reload truststore from disk!", e);
        }
    }

    @Override
    public void checkClientTrusted(X509Certificate[] chain, String authType) throws CertificateException {
        currentTrustManager.checkClientTrusted(chain, authType);
    }

    @Override
    public void checkServerTrusted(X509Certificate[] chain, String authType) throws CertificateException {
        currentTrustManager.checkServerTrusted(chain, authType);
    }

    @Override
    public X509Certificate[] getAcceptedIssuers() {
        return currentTrustManager.getAcceptedIssuers();
    }

    @Override
    public void checkClientTrusted(X509Certificate[] chain, String authType, Socket socket) throws CertificateException {
        currentTrustManager.checkClientTrusted(chain, authType, socket);
    }

    @Override
    public void checkServerTrusted(X509Certificate[] chain, String authType, Socket socket) throws CertificateException {
        currentTrustManager.checkServerTrusted(chain, authType, socket);
    }

    @Override
    public void checkClientTrusted(X509Certificate[] chain, String authType, SSLEngine engine) throws CertificateException {
        currentTrustManager.checkClientTrusted(chain, authType, engine);
    }

    @Override
    public void checkServerTrusted(X509Certificate[] chain, String authType, SSLEngine engine) throws CertificateException {
        currentTrustManager.checkServerTrusted(chain, authType, engine);
    }
}
""",

    # 8. com.ftgo.kitchen.security.ReloadableX509KeyManager
    "src/main/java/com/ftgo/kitchen/security/ReloadableX509KeyManager.java": """package com.ftgo.kitchen.security;

import javax.net.ssl.X509ExtendedKeyManager;
import javax.net.ssl.KeyManagerFactory;
import java.io.File;
import java.io.FileInputStream;
import java.security.KeyStore;
import java.security.Principal;
import java.security.PrivateKey;
import java.security.cert.X509Certificate;
import java.net.Socket;
import javax.net.ssl.SSLEngine;

public class ReloadableX509KeyManager extends X509ExtendedKeyManager {
    private final String keystorePath;
    private final String password;
    private final String alias;
    private X509ExtendedKeyManager currentKeyManager;

    public ReloadableX509KeyManager(String keystorePath, String password, String alias) {
        this.keystorePath = keystorePath;
        this.password = password;
        this.alias = alias;
        reload();
    }

    public synchronized void reload() {
        try {
            KeyStore keyStore = KeyStore.getInstance("PKCS12");
            try (FileInputStream fis = new FileInputStream(new File(keystorePath))) {
                keyStore.load(fis, password.toCharArray());
            }
            KeyManagerFactory kmf = KeyManagerFactory.getInstance(KeyManagerFactory.getDefaultAlgorithm());
            kmf.init(keyStore, password.toCharArray());
            for (javax.net.ssl.KeyManager km : kmf.getKeyManagers()) {
                if (km instanceof X509ExtendedKeyManager) {
                    this.currentKeyManager = (X509ExtendedKeyManager) km;
                    break;
                }
            }
        } catch (Exception e) {
            throw new IllegalStateException("Failed to reload keystore from disk!", e);
        }
    }

    @Override
    public String[] getClientAliases(String keyType, Principal[] issuers) {
        return currentKeyManager.getClientAliases(keyType, issuers);
    }

    @Override
    public String chooseClientAlias(String[] keyType, Principal[] issuers, Socket socket) {
        return alias;
    }

    @Override
    public String[] getServerAliases(String keyType, Principal[] issuers) {
        return currentKeyManager.getServerAliases(keyType, issuers);
    }

    @Override
    public String chooseServerAlias(String keyType, Principal[] issuers, Socket socket) {
        return alias;
    }

    @Override
    public X509Certificate[] getCertificateChain(String alias) {
        return currentKeyManager.getCertificateChain(alias);
    }

    @Override
    public PrivateKey getPrivateKey(String alias) {
        return currentKeyManager.getPrivateKey(alias);
    }

    @Override
    public String chooseEngineClientAlias(String[] keyType, Principal[] issuers, SSLEngine engine) {
        return alias;
    }

    @Override
    public String chooseEngineServerAlias(String keyType, Principal[] issuers, SSLEngine engine) {
        return alias;
    }
}
""",

    # 9. com.ftgo.kitchen.security.CertificateReloadScheduler
    "src/main/java/com/ftgo/kitchen/security/CertificateReloadScheduler.java": """package com.ftgo.kitchen.security;

import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import java.io.File;

@Component
public class CertificateReloadScheduler {

    private final ReloadableX509KeyManager keyManager;
    private final ReloadableX509TrustManager trustManager;

    private long lastKeyManagerModified;
    private long lastTrustManagerModified;

    public CertificateReloadScheduler(ReloadableX509KeyManager keyManager, ReloadableX509TrustManager trustManager) {
        this.keyManager = keyManager;
        this.trustManager = trustManager;
        this.lastKeyManagerModified = new File("/var/certs/kitchen-keystore.p12").lastModified();
        this.lastTrustManagerModified = new File("/var/certs/kitchen-truststore.p12").lastModified();
    }

    @Scheduled(fixedDelay = 60000)
    public void checkForUpdates() {
        File keyFile = new File("/var/certs/kitchen-keystore.p12");
        if (keyFile.exists() && keyFile.lastModified() > lastKeyManagerModified) {
            keyManager.reload();
            lastKeyManagerModified = keyFile.lastModified();
        }

        File trustFile = new File("/var/certs/kitchen-truststore.p12");
        if (trustFile.exists() && trustFile.lastModified() > lastTrustManagerModified) {
            trustManager.reload();
            lastTrustManagerModified = trustFile.lastModified();
        }
    }
}
""",

    # 10. com.ftgo.order.controller.OrderController
    "src/main/java/com/ftgo/order/controller/OrderController.java": """package com.ftgo.order.controller;

import com.ftgo.kitchen.model.Order;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class OrderController {

    @GetMapping("/v1/orders/{orderId}")
    public Order getOrder(@PathVariable String orderId) {
        return new Order(orderId, "APPROVED");
    }
}
""",

    # 11. com.ftgo.order.MtlsSecurityApplication
    "src/main/java/com/ftgo/order/MtlsSecurityApplication.java": """package com.ftgo.order;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cloud.openfeign.EnableFeignClients;

@SpringBootApplication
@EnableFeignClients(basePackages = "com.ftgo.kitchen.client")
public class MtlsSecurityApplication {
    public static void main(String[] args) {
        SpringApplication.run(MtlsSecurityApplication.class, args);
    }
}
""",

    # 12. com.ftgo.order.MtlsServiceIntegrationTest (Tests)
    "src/test/java/com/ftgo/order/MtlsServiceIntegrationTest.java": """package com.ftgo.order;

import org.junit.jupiter.api.Assertions;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.core.io.ClassPathResource;
import org.springframework.http.ResponseEntity;
import org.springframework.http.client.HttpComponentsClientHttpRequestFactory;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestTemplate;

import javax.net.ssl.SSLContext;
import java.io.InputStream;
import java.security.KeyStore;
import org.apache.http.impl.client.CloseableHttpClient;
import org.apache.http.impl.client.HttpClients;
import org.apache.http.ssl.SSLContexts;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
public class MtlsServiceIntegrationTest {

    @LocalServerPort
    private int port;

    @Test
    public void testConnectWithClientCertificate_Succeeds() throws Exception {
        KeyStore keyStore = KeyStore.getInstance("PKCS12");
        try (InputStream ksStream = new ClassPathResource("kitchen-keystore.p12").getInputStream()) {
            keyStore.load(ksStream, "password".toCharArray());
        }

        KeyStore trustStore = KeyStore.getInstance("PKCS12");
        try (InputStream tsStream = new ClassPathResource("kitchen-truststore.p12").getInputStream()) {
            trustStore.load(tsStream, "password".toCharArray());
        }

        SSLContext sslContext = SSLContexts.custom()
                .loadKeyMaterial(keyStore, "password".toCharArray())
                .loadTrustMaterial(trustStore, null)
                .build();

        CloseableHttpClient httpClient = HttpClients.custom()
                .setSSLContext(sslContext)
                .build();

        RestTemplate secureTemplate = new RestTemplate(new HttpComponentsClientHttpRequestFactory(httpClient));

        ResponseEntity<String> response = secureTemplate.getForEntity(
            "https://localhost:" + port + "/v1/orders/order-100", String.class
        );

        Assertions.assertEquals(200, response.getStatusCode().value());
    }

    @Test
    public void testConnectWithoutClientCertificate_Fails() {
        RestTemplate plaintextTemplate = new RestTemplate();

        Assertions.assertThrows(ResourceAccessException.class, () -> {
            plaintextTemplate.getForEntity(
                "https://localhost:" + port + "/v1/orders/order-100", String.class
            );
        });
    }
}
"""
}

# Write files
for rel_path, content in files_dict.items():
    abs_path = os.path.join(base_path, rel_path.replace("/", os.sep))
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
    with open(abs_path, "w", encoding="utf-8") as f:
        f.write(content.strip() + "\\n")
    print(f"Created file: {rel_path}")

print("All Java source assets written successfully!")
