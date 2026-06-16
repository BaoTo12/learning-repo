package com.springkafka.course.fraud;

import com.springkafka.course.avro.FraudCheckEvent;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;

@Service
public class FraudService {
    private static final Logger log = LoggerFactory.getLogger(FraudService.class);

    private final KafkaTemplate<String, Object> kafkaTemplate;

    public FraudService(KafkaTemplate<String, Object> kafkaTemplate) {
        this.kafkaTemplate = kafkaTemplate;
    }

    @KafkaListener(topics = "fraud-commands", groupId = "fraud-service-group")
    public void executeFraudCheck(FraudCheckEvent event) {
        log.info("FRAUD SERVICE -> Executing limits and security checks for Transfer ID: {}", event.getTransferId());

        String transferId = event.getTransferId().toString();
        FraudCheckEvent reply;

        if (transferId.contains("SUSPICIOUS")) {
            log.error("FRAUD SERVICE -> Security check failed! suspicious transaction pattern detected for ID: {}", transferId);
            reply = FraudCheckEvent.newBuilder(event)
                    .setStatus("REJECTED")
                    .setReason("Suspicious pattern trigger limit")
                    .build();
        } else {
            log.info("FRAUD SERVICE -> Transaction approved for ID: {}", transferId);
            reply = FraudCheckEvent.newBuilder(event)
                    .setStatus("APPROVED")
                    .setReason("Clear risk profile")
                    .build();
        }

        kafkaTemplate.send("fraud-replies", transferId, reply);
    }
}
