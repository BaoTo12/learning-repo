package com.springkafka.course;

import com.springkafka.course.avro.TransferEvent;
import com.springkafka.course.outbox.TransferService;
import org.junit.jupiter.api.Disabled;
import org.junit.jupiter.api.Test;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.KafkaContainer;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;

import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

@SpringBootTest
@Testcontainers
@Disabled("Disabled by default because running Testcontainers requires an active Docker daemon")
public class MoneyTransferE2eTest {
    private static final Logger log = LoggerFactory.getLogger(MoneyTransferE2eTest.class);

    @Container
    public static PostgreSQLContainer<?> postgres = new PostgreSQLContainer<>("postgres:15-alpine")
            .withDatabaseName("ledger_db")
            .withUsername("postgres")
            .withPassword("secret_pass");

    @Container
    public static KafkaContainer kafka = new KafkaContainer(
            DockerImageName.parse("confluentinc/cp-kafka:7.6.0")
    );

    @DynamicPropertySource
    public static void configureProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url", postgres::getJdbcUrl);
        registry.add("spring.datasource.username", postgres::getUsername);
        registry.add("spring.datasource.password", postgres::getPassword);
        registry.add("spring.kafka.bootstrap-servers", kafka::getBootstrapServers);
        // Bind to a mocked Schema Registry scope for fast local verification in tests
        registry.add("spring.kafka.properties.schema.registry.url", () -> "mock://test-scope");
    }

    @Autowired
    private TransferService transferService;

    // Static latches and response store to bridge between Kafka consumer threads and the test thread
    private static final ConcurrentHashMap<String, String> finalStatuses = new ConcurrentHashMap<>();
    private static final ConcurrentHashMap<String, CountDownLatch> latches = new ConcurrentHashMap<>();

    @Test
    public void testSuccessfulTransferSaga() throws InterruptedException {
        String sender = "account-1";
        String receiver = "account-2";
        double amount = 100.0;

        CountDownLatch latch = new CountDownLatch(1);
        String transferId = transferService.initiateTransfer(sender, receiver, amount);
        latches.put(transferId, latch);

        log.info("TEST -> Wait for Transfer: {} to complete", transferId);
        boolean completed = latch.await(20, TimeUnit.SECONDS);

        assertTrue(completed, "Transfer Saga did not complete in time!");
        assertEquals("APPROVED", finalStatuses.get(transferId));
        log.info("TEST -> Successful saga verification complete!");
    }

    @Test
    public void testSuspiciousTransferTriggersFraudRollback() throws InterruptedException {
        String sender = "account-SUSPICIOUS-99";
        String receiver = "account-3";
        double amount = 5000.0;

        CountDownLatch latch = new CountDownLatch(1);
        String transferId = transferService.initiateTransfer(sender, receiver, amount);
        latches.put(transferId, latch);

        log.info("TEST -> Wait for suspicious Transfer: {} to roll back", transferId);
        boolean completed = latch.await(20, TimeUnit.SECONDS);

        assertTrue(completed, "Transfer Saga did not rollback in time!");
        assertEquals("FAILED", finalStatuses.get(transferId));
        log.info("TEST -> Fraud rollback compensation verification complete!");
    }

    // Helper Test Listener capturing notifications
    @org.springframework.stereotype.Component
    public static class TestNotificationListener {
        @KafkaListener(topics = "transfer-notifications", groupId = "test-verification-group")
        public void listenNotification(TransferEvent event) {
            String transferId = event.getTransferId().toString();
            String status = event.getStatus().toString();
            log.info("TEST LISTENER -> Received status notification for transfer: {} -> {}", transferId, status);

            finalStatuses.put(transferId, status);
            CountDownLatch latch = latches.get(transferId);
            if (latch != null) {
                latch.countDown();
            }
        }
    }
}
