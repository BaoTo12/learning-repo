package com.chibao.edu.adapter.out.persistence;

import com.chibao.edu.application.domain.model.Account;
import com.chibao.edu.application.domain.model.Activity;
import com.chibao.edu.application.domain.model.ActivityWindow;
import com.chibao.edu.application.domain.model.Money;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.List;

@Component
class AccountMapper {

    Account mapToDomainEntity(
            AccountJpaEntity account,
            List<ActivityJpaEntity> activities,
            Long withdrawalBalance,
            Long depositBalance) {

        Money baselineBalance = Money.subtract(
                Money.of(depositBalance),
                Money.of(withdrawalBalance));

        return Account.withId(
                new Account.AccountId(account.getId()),
                baselineBalance,
                mapToActivityWindow(activities));

    }

    ActivityWindow mapToActivityWindow(List<ActivityJpaEntity> activities) {
        List<Activity> mappedActivities = new ArrayList<>();

        for (ActivityJpaEntity activity : activities) {
            mappedActivities.add(new Activity(
                    new Activity.ActivityId(activity.getId()),
                    new Account.AccountId(activity.getOwnerAccountId()),
                    new Account.AccountId(activity.getSourceAccountId()),
                    new Account.AccountId(activity.getTargetAccountId()),
                    activity.getTimestamp(),
                    Money.of(activity.getAmount())));
        }

        return new ActivityWindow(mappedActivities);
    }

    ActivityJpaEntity mapToJpaEntity(Activity activity) {
        return new ActivityJpaEntity(
                activity.getId() == null ? null : activity.getId().getValue(),
                activity.getTimestamp(),
                activity.getOwnerAccountId().getValue(),
                activity.getSourceAccountId().getValue(),
                activity.getTargetAccountId().getValue(),
                activity.getMoney().getAmount().longValue());
    }

}
