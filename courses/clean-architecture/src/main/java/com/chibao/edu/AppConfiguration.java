package com.chibao.edu;

import com.chibao.edu.application.domain.model.Money;
import com.chibao.edu.application.domain.service.MoneyTransferProperties;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
@EnableConfigurationProperties(AppConfigurationProperties.class)
public class AppConfiguration {
    /**
     * Adds a use-case-specific {@link MoneyTransferProperties} object to the application context. The properties
     * are read from the Spring-Boot-specific {@link AppConfigurationProperties} object.
     */
    @Bean
    public MoneyTransferProperties moneyTransferProperties(AppConfigurationProperties appConfigurationProperties){
        return new MoneyTransferProperties(Money.of(appConfigurationProperties.getTransferThreshold()));
    }
}
