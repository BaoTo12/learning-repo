package com.chibao.edu.application.domain.service;

import com.chibao.edu.application.domain.model.Account;
import com.chibao.edu.application.port.in.SendMoneyCommand;
import com.chibao.edu.application.port.in.SendMoneyUseCase;
import com.chibao.edu.application.port.out.AccountLock;
import com.chibao.edu.application.port.out.LoadAccountPort;
import com.chibao.edu.application.port.out.UpdateAccountStatePort;
import lombok.RequiredArgsConstructor;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

@Transactional
@RequiredArgsConstructor
public class SendMoneyService implements SendMoneyUseCase {
    private final LoadAccountPort loadAccountPort;
    private final AccountLock accountLock;
    private final UpdateAccountStatePort updateAccountStatePort;
    private final MoneyTransferProperties moneyTransferProperties;


    @Override
    public boolean sendMoney(SendMoneyCommand command) {

        checkThreshold(command);

        LocalDateTime baselineDate = LocalDateTime.now().minusDays(10);

        Account sourceAccount = loadAccountPort.loadAccount(
                command.sourceAccountId(),
                baselineDate);

        Account targetAccount = loadAccountPort.loadAccount(
                command.targetAccountId(),
                baselineDate);

        Account.AccountId sourceAccountId = sourceAccount.getId()
                .orElseThrow(() -> new IllegalStateException("expected source account ID not to be empty"));
        Account.AccountId targetAccountId = targetAccount.getId()
                .orElseThrow(() -> new IllegalStateException("expected target account ID not to be empty"));

        accountLock.lockAccount(sourceAccountId);
        if (!sourceAccount.withdraw(command.money(), targetAccountId)) {
            accountLock.releaseAccount(sourceAccountId);
            return false;
        }

        accountLock.lockAccount(targetAccountId);
        if (!targetAccount.deposit(command.money(), sourceAccountId)) {
            accountLock.releaseAccount(sourceAccountId);
            accountLock.releaseAccount(targetAccountId);
            return false;
        }

        updateAccountStatePort.updateActivities(sourceAccount);
        updateAccountStatePort.updateActivities(targetAccount);

        accountLock.releaseAccount(sourceAccountId);
        accountLock.releaseAccount(targetAccountId);
        return true;
    }

    private void checkThreshold(SendMoneyCommand command) {
        if(command.money().isGreaterThan(moneyTransferProperties.getMaximumTransferThreshold())){
            throw new ThresholdExceededException(moneyTransferProperties.getMaximumTransferThreshold(), command.money());
        }
    }

}
