package com.chibao.edu.application.port.out;

import com.chibao.edu.application.domain.model.Account;

public interface AccountLock {

    void lockAccount(Account.AccountId accountId);

    void releaseAccount(Account.AccountId accountId);

}
