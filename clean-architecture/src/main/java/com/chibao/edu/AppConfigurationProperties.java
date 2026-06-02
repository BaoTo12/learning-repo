package com.chibao.edu;

import lombok.Data;
import org.springframework.boot.context.properties.ConfigurationProperties;

@Data
@ConfigurationProperties(prefix = "chibao")
public class AppConfigurationProperties {
    private long transferThreshold = Long.MAX_VALUE;
}