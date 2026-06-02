package com.chibao.edu.application.port.out;

import com.chibao.edu.application.domain.model.Account;

import java.time.LocalDateTime;

public interface LoadAccountPort {

    Account loadAccount(Account.AccountId accountId, LocalDateTime baselineDate);
}
