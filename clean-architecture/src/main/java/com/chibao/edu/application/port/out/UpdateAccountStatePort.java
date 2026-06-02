package com.chibao.edu.application.port.out;

import com.chibao.edu.application.domain.model.Account;

public interface UpdateAccountStatePort {

    void updateActivities(Account account);

}
