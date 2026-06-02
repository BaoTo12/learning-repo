package com.chibao.edu.application.port.in;

import com.chibao.edu.application.domain.model.Account;
import com.chibao.edu.application.domain.model.Money;
import jakarta.validation.constraints.NotNull;

import static com.chibao.edu.common.validation.Validator.validate;

public record SendMoneyCommand(
        @NotNull Account.AccountId sourceAccountId,
        @NotNull Account.AccountId targetAccountId,
        @NotNull  @PositiveMoney Money money
) {

    public SendMoneyCommand(
            Account.AccountId sourceAccountId,
            Account.AccountId targetAccountId,
            Money money) {
        this.sourceAccountId = sourceAccountId;
        this.targetAccountId = targetAccountId;
        this.money = money;
        validate(this);
    }

}