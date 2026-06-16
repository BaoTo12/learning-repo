package com.springkafka.course.saga;

import com.springkafka.course.avro.BalanceHoldEvent;
import com.springkafka.course.avro.FraudCheckEvent;
import com.springkafka.course.avro.TransferEvent;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class TransferSagaOrchestrator {
    private static final Logger log = LoggerFactory.getLogger(TransferSagaOrchestrator.class);

    private final KafkaTemplate<String, Object> kafkaTemplate;

    public TransferSagaOrchestrator(KafkaTemplate<String, Object> kafkaTemplate) {
        this.kafkaTemplate = kafkaTemplate;
    }

    // 1. Listen for new Transfer Request from Outbox
    @KafkaListener(topics = "transfer-outbox", groupId = "saga-orchestrator-group")
    @Transactional
    public void handleTransferRequested(TransferEvent event) {
        log.info("SAGA ORCHESTRATOR -> Initiating Saga for Transfer: {}", event.getTransferId());

        BalanceHoldEvent holdCommand = BalanceHoldEvent.newBuilder()
                .setTransferId(event.getTransferId())
                .setAccountId(event.getSenderId())
                .setAmount(event.getAmount())
                .setStatus("PENDING")
                .build();

        log.info("SAGA ORCHESTRATOR -> Sending balance lock command for Transfer: {}", event.getTransferId());
        kafkaTemplate.send("balance-commands", event.getTransferId().toString(), holdCommand);
    }

    // 2. Listen for Balance Hold status updates
    @KafkaListener(topics = "balance-replies", groupId = "saga-orchestrator-group")
    @Transactional
    public void handleBalanceReply(BalanceHoldEvent event) {
        log.info("SAGA ORCHESTRATOR -> Balance Hold Reply received for Transfer: {} with status: {}", 
                event.getTransferId(), event.getStatus());

        if ("HELD".equals(event.getStatus().toString())) {
            log.info("SAGA ORCHESTRATOR -> Balance HELD. Triggering Fraud Check.");
            
            FraudCheckEvent fraudCommand = FraudCheckEvent.newBuilder()
                    .setTransferId(event.getTransferId())
                    .setStatus("PENDING")
                    .setReason("Standard limit check")
                    .build();

            kafkaTemplate.send("fraud-commands", event.getTransferId().toString(), fraudCommand);
        } else if ("FAILED".equals(event.getStatus().toString())) {
            log.warn("SAGA ORCHESTRATOR -> Balance hold failed! Declining transfer.");
            
            TransferEvent failureEvent = TransferEvent.newBuilder()
                    .setTransferId(event.getTransferId())
                    .setSenderId(event.getAccountId())
                    .setReceiverId("UNKNOWN")
                    .setAmount(event.getAmount())
                    .setStatus("FAILED")
                    .build();
            
            kafkaTemplate.send("transfer-notifications", event.getTransferId().toString(), failureEvent);
        }
    }

    // 3. Listen for Fraud Validation checks outcome
    @KafkaListener(topics = "fraud-replies", groupId = "saga-orchestrator-group")
    @Transactional
    public void handleFraudReply(FraudCheckEvent event) {
        log.info("SAGA ORCHESTRATOR -> Fraud Reply received for Transfer: {} with status: {}", 
                event.getTransferId(), event.getStatus());

        if ("APPROVED".equals(event.getStatus().toString())) {
            log.info("SAGA ORCHESTRATOR -> Fraud Check APPROVED. finalising transfer.");

            // Confirming hold and triggering transfer resolution
            BalanceHoldEvent releaseConfirm = BalanceHoldEvent.newBuilder()
                    .setTransferId(event.getTransferId())
                    .setAccountId("CONFIRMED")
                    .setAmount(0.0)
                    .setStatus("RELEASED")
                    .build();

            kafkaTemplate.send("balance-commands", event.getTransferId().toString(), releaseConfirm);

            TransferEvent successEvent = TransferEvent.newBuilder()
                    .setTransferId(event.getTransferId())
                    .setSenderId("SENDER")
                    .setReceiverId("RECEIVER")
                    .setAmount(0.0)
                    .setStatus("APPROVED")
                    .build();

            kafkaTemplate.send("transfer-notifications", event.getTransferId().toString(), successEvent);
            
        } else if ("REJECTED".equals(event.getStatus().toString())) {
            log.error("SAGA ORCHESTRATOR -> Fraud check REJECTED! Triggering compensating action: Release Balance.");

            // COMPENSATING TRANSACTION: Release the locked money
            BalanceHoldEvent rollbackHold = BalanceHoldEvent.newBuilder()
                    .setTransferId(event.getTransferId())
                    .setAccountId("ROLLBACK")
                    .setAmount(0.0)
                    .setStatus("RELEASED")
                    .build();

            kafkaTemplate.send("balance-commands", event.getTransferId().toString(), rollbackHold);

            // Record transfer failure
            TransferEvent rollbackEvent = TransferEvent.newBuilder()
                    .setTransferId(event.getTransferId())
                    .setSenderId("SENDER")
                    .setReceiverId("RECEIVER")
                    .setAmount(0.0)
                    .setStatus("FAILED")
                    .build();

            kafkaTemplate.send("transfer-notifications", event.getTransferId().toString(), rollbackEvent);
        }
    }
}
