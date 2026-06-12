package com.chibao.japlearning.JpaQueriesType;

import jakarta.persistence.*;

public class TestClass {

    @PersistenceContext
    private EntityManager entityManager;

    public UserEntity getUserByIdPlainQuery(Long id) {
        Query jqlQuery = entityManager.createQuery("SELECT u FROM UserEntity u WHERE u.id=:id");
        jqlQuery.setParameter("id", id);
        return (UserEntity) jqlQuery.getSingleResult();
    }

    public UserEntity getUserByIdWithTypedQuery(Long id) {
        TypedQuery<UserEntity> typedQuery
                = entityManager.createQuery("SELECT u FROM UserEntity u WHERE u.id=:id", UserEntity.class);
        typedQuery.setParameter("id", id);
        return typedQuery.getSingleResult();
    }

    public UserEntity getUserByIdWithNamedQuery(Long id) {
        Query namedQuery = entityManager.createNamedQuery("UserEntity.findByUserId");
        namedQuery.setParameter("userId", id);
        return (UserEntity) namedQuery.getSingleResult();
    }

    public UserEntity getUserByIdWithNativeQuery(Long id) {
        Query nativeQuery
                = entityManager.createNativeQuery("SELECT * FROM users WHERE id=:userId", UserEntity.class);
        nativeQuery.setParameter("userId", id);
        return (UserEntity) nativeQuery.getSingleResult();
    }
}
