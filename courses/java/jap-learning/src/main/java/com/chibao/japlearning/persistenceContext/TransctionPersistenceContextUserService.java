package com.chibao.japlearning.persistenceContext;

import jakarta.persistence.EntityManager;
import jakarta.persistence.PersistenceContext;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

@Component
public class TransctionPersistenceContextUserService {
    @PersistenceContext
    private EntityManager entityManager;

    @Transactional
    public User insertWithTransaction(User user) {
        entityManager.persist(user);
        return user;
    }
    public User insertWithoutTransaction(User user) {
        entityManager.persist(user);
        return user;
    }

    public User find(long id) {
        return entityManager.find(User.class, id);
    }
}
