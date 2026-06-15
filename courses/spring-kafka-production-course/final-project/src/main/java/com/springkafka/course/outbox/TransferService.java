package com.springkafka.course.outbox;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.UUID;

@Service
public class TransferService {
    private static final Logger log = LoggerFactory.getLogger(TransferService.class);

    private final OutboxRepository outboxRepository;
    private final ObjectMapper objectMapper;

    public TransferService(OutboxRepository outboxRepository, ObjectMapper objectMapper) {
        this.outboxRepository = outboxRepository;
        this.objectMapper = objectMapper;
    }

    @Transactional
    public String initiateTransfer(String senderId, String receiverId, double amount) {
        String transferId = UUID.randomUUID().toString();
        log.info("TRANSFER SERVICE -> Initiating transfer request of ${} from {} to {}", amount, senderId, receiverId);

        try {
            // Define outbox payload details
            OutboxPublisher.TransferPayload payload = new OutboxPublisher.TransferPayload();
            payload.setTransferId(transferId);
            payload.setSenderId(senderId);
            payload.setReceiverId(receiverId);
            payload.setAmount(amount);

            String eventPayload = objectMapper.writeValueAsString(payload);

            // Persist the outbox record (co-located in the same database transaction)
            OutboxEvent outbox = new OutboxEvent(
                    UUID.randomUUID().toString(),
                    "transfer", 
                    transferId, 
                    "TransferRequested",
                    eventPayload
            );

            outboxRepository.save(outbox);
            log.info("TRANSFER SERVICE -> Outbox record saved atomically for transfer ID: {}", transferId);
            return transferId;

        } catch (Exception e) {
            log.error("TRANSFER SERVICE -> Failed to initiate transfer", e);
            throw new RuntimeException("Database save failed", e);
        }
    }
}
