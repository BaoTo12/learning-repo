package com.springkafka.course.balance;

import com.springkafka.course.avro.BalanceHoldEvent;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.kafka.annotation.DltHandler;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.annotation.RetryableTopic;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.retry.annotation.Backoff;
import org.springframework.stereotype.Service;

import java.net.ConnectException;

@Service
public class BalanceService {
    private static final Logger log = LoggerFactory.getLogger(BalanceService.class);

    private final KafkaTemplate<String, Object> kafkaTemplate;

    public BalanceService(KafkaTemplate<String, Object> kafkaTemplate) {
        this.kafkaTemplate = kafkaTemplate;
    }

    // Process balance commands with non-blocking retries
    @RetryableTopic(
            attempts = "3",
            backoff = @Backoff(delay = 1000, multiplier = 2.0),
            include = { ConnectException.class, RuntimeException.class }
    )
    @KafkaListener(topics = "balance-commands", groupId = "balance-service-group")
    public void processBalanceCommand(BalanceHoldEvent event) throws ConnectException {
        log.info("BALANCE SERVICE -> Received command for Transfer: {}, Account: {}, Status: {}, Amount: {}",
                event.getTransferId(), event.getAccountId(), event.getStatus(), event.getAmount());

        String accountId = event.getAccountId().toString();
        String status = event.getStatus().toString();

        if ("PENDING".equals(status)) {
            // Check for simulated network failure to verify retries
            if (accountId.contains("NETWORK_FAIL")) {
                log.warn("BALANCE SERVICE -> Simulated network failure! Throwing ConnectException for retry validation.");
                throw new ConnectException("Simulated connection timeout to ledger store database");
            }
            
            // Check for simulated business failure
            if (accountId.contains("INSUFFICIENT_FUNDS")) {
                log.error("BALANCE SERVICE -> Account has insufficient funds!");
                
                BalanceHoldEvent failedEvent = BalanceHoldEvent.newBuilder(event)
                        .setStatus("FAILED")
                        .build();
                kafkaTemplate.send("balance-replies", event.getTransferId().toString(), failedEvent);
                return;
            }

            // Normal flow: Hold the balance
            log.info("BALANCE SERVICE -> Balance locked ${} successfully for account: {}", event.getAmount(), accountId);
            BalanceHoldEvent heldEvent = BalanceHoldEvent.newBuilder(event)
                    .setStatus("HELD")
                    .build();
            kafkaTemplate.send("balance-replies", event.getTransferId().toString(), heldEvent);

        } else if ("RELEASED".equals(status)) {
            if ("ROLLBACK".equals(accountId)) {
                log.warn("BALANCE SERVICE COMPENSATING TRANSACTION -> Releasing locked balance and refunding customer. Transfer ID: {}",
                        event.getTransferId());
            } else {
                log.info("BALANCE SERVICE -> Finalizing transaction. Releasing balance locks. Transfer ID: {}", 
                        event.getTransferId());
            }

            BalanceHoldEvent releasedEvent = BalanceHoldEvent.newBuilder(event)
                    .setStatus("RELEASED")
                    .build();
            kafkaTemplate.send("balance-replies", event.getTransferId().toString(), releasedEvent);
        }
    }

    @DltHandler
    public void handleDlt(BalanceHoldEvent event, @org.springframework.messaging.handler.annotation.Header(org.springframework.kafka.support.KafkaHeaders.RECEIVED_TOPIC) String topic) {
        log.error("BALANCE SERVICE DLT -> Message failed retries and reached DLT. Topic: {}, TransferId: {}", 
                topic, event.getTransferId());
    }
}
