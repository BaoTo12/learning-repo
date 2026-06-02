package com.chibao.edu.application.domain.service;

import com.chibao.edu.application.domain.model.Money;
import com.chibao.edu.application.port.in.GetAccountBalanceUseCase;
import com.chibao.edu.application.port.out.LoadAccountPort;
import lombok.RequiredArgsConstructor;

import java.time.LocalDateTime;

@RequiredArgsConstructor
public class GetAccountBalanceService implements GetAccountBalanceUseCase {
    private final LoadAccountPort loadAccountPort;

    @Override
    public Money getAccountBalance(GetAccountBalanceQuery query) {
        return loadAccountPort.loadAccount(query.accountId(), LocalDateTime.now())
                .calculateBalance();
    }
}
