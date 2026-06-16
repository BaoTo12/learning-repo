package com.springkafka.course.outbox;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/transfers")
public class TransferController {

    private final TransferService transferService;

    public TransferController(TransferService transferService) {
        this.transferService = transferService;
    }

    @PostMapping
    public ResponseEntity<String> createTransfer(@RequestParam String senderId,
                                                 @RequestParam String receiverId,
                                                 @RequestParam double amount) {
        String transferId = transferService.initiateTransfer(senderId, receiverId, amount);
        return ResponseEntity.ok("Transfer initiated with ID: " + transferId);
    }
}
