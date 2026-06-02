package com.chibao.edu.application.port.in;

import com.chibao.edu.application.domain.model.Account;
import com.chibao.edu.application.domain.model.Money;

public interface GetAccountBalanceUseCase {

    Money getAccountBalance(GetAccountBalanceQuery query);

    // this is input model for this incoming port
    record GetAccountBalanceQuery(Account.AccountId accountId) {
    }
}