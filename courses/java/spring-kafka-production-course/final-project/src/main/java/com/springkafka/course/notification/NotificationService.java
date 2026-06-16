package com.springkafka.course.notification;

import com.springkafka.course.avro.TransferEvent;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Service;

@Service
public class NotificationService {
    private static final Logger log = LoggerFactory.getLogger(NotificationService.class);

    @KafkaListener(topics = "transfer-notifications", groupId = "notification-service-group")
    public void processNotification(TransferEvent event) {
        log.info("NOTIFICATION SERVICE [read_committed] -> Transaction execution finished. Event details - " +
                "Transfer ID: {}, Status: {}, Amount: {}", 
                event.getTransferId(), event.getStatus(), event.getAmount());
        
        if ("APPROVED".equals(event.getStatus().toString())) {
            log.info("NOTIFICATION SERVICE -> Money transfer completed successfully! Dispatching receipt notification.");
        } else {
            log.warn("NOTIFICATION SERVICE -> Money transfer failed! Dispatching transaction cancellation notice.");
        }
    }
}
