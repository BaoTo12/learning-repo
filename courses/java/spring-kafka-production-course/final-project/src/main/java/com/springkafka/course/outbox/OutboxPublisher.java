package com.springkafka.course.outbox;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.springkafka.course.avro.TransferEvent;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;

@Service
public class OutboxPublisher {
    private static final Logger log = LoggerFactory.getLogger(OutboxPublisher.class);

    private final OutboxRepository outboxRepository;
    private final KafkaTemplate<String, TransferEvent> kafkaTemplate;
    private final ObjectMapper objectMapper;

    public OutboxPublisher(OutboxRepository outboxRepository,
                           KafkaTemplate<String, TransferEvent> kafkaTemplate,
                           ObjectMapper objectMapper) {
        this.outboxRepository = outboxRepository;
        this.kafkaTemplate = kafkaTemplate;
        this.objectMapper = objectMapper;
    }

    @Scheduled(fixedDelay = 2000)
    @Transactional
    public void publishPendingEvents() {
        List<OutboxEvent> pendingEvents = outboxRepository.findByProcessedFalseOrderByCreatedAtAsc();
        if (pendingEvents.isEmpty()) {
            return;
        }

        log.info("OUTBOX PUBLISHER -> Found {} pending outbox events to publish", pendingEvents.size());

        for (OutboxEvent event : pendingEvents) {
            try {
                if ("TransferRequested".equals(event.getEventType())) {
                    // Parse the JSON payload back to fields
                    TransferPayload payload = objectMapper.readValue(event.getPayload(), TransferPayload.class);

                    // Map fields into generated Avro TransferEvent
                    TransferEvent avroEvent = TransferEvent.newBuilder()
                            .setTransferId(payload.getTransferId())
                            .setSenderId(payload.getSenderId())
                            .setReceiverId(payload.getReceiverId())
                            .setAmount(payload.getAmount())
                            .setStatus("PENDING")
                            .build();

                    log.info("OUTBOX PUBLISHER -> Publishing TransferEvent to Kafka. ID: {}", avroEvent.getTransferId());
                    
                    // Publish to Kafka outbox topic
                    kafkaTemplate.send("transfer-outbox", avroEvent.getTransferId().toString(), avroEvent).get();
                }

                // Mark outbox record as processed
                event.setProcessed(true);
                outboxRepository.save(event);

            } catch (Exception e) {
                log.error("OUTBOX PUBLISHER -> Failed to publish outbox event: " + event.getEventId(), e);
                // Keep processed=false so it retries on the next execution cycle
            }
        }
    }

    // Helper static class for JSON parsing mapping
    public static class TransferPayload {
        private String transferId;
        private String senderId;
        private String receiverId;
        private double amount;

        public TransferPayload() {}

        public String getTransferId() { return transferId; }
        public void setTransferId(String transferId) { this.transferId = transferId; }

        public String getSenderId() { return senderId; }
        public void setSenderId(String senderId) { this.senderId = senderId; }

        public String getReceiverId() { return receiverId; }
        public void setReceiverId(String receiverId) { this.receiverId = receiverId; }

        public double getAmount() { return amount; }
        public void setAmount(double amount) { this.amount = amount; }
    }
}
