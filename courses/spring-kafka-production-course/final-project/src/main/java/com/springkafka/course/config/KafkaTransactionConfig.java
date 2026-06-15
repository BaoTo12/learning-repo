package com.springkafka.course.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.config.ConcurrentKafkaListenerContainerFactory;
import org.springframework.kafka.core.ConsumerFactory;
import org.springframework.kafka.core.ProducerFactory;
import org.springframework.kafka.transaction.KafkaTransactionManager;
import org.springframework.boot.autoconfigure.kafka.ConcurrentKafkaListenerContainerFactoryConfigurer;

@Configuration
public class KafkaTransactionConfig {

    @Bean
    public KafkaTransactionManager<Object, Object> kafkaTransactionManager(
            ProducerFactory<Object, Object> producerFactory) {
        return new KafkaTransactionManager<>(producerFactory);
    }

    @Bean
    public ConcurrentKafkaListenerContainerFactory<Object, Object> kafkaListenerContainerFactory(
            ConcurrentKafkaListenerContainerFactoryConfigurer configurer,
            ConsumerFactory<Object, Object> consumerFactory,
            KafkaTransactionManager<Object, Object> transactionManager) {
        
        ConcurrentKafkaListenerContainerFactory<Object, Object> factory = 
                new ConcurrentKafkaListenerContainerFactory<>();
        configurer.configure(factory, consumerFactory);
        // Bind the Kafka Transaction Manager to container listeners for transactional processing
        factory.getContainerProperties().setTransactionManager(transactionManager);
        return factory;
    }
}
