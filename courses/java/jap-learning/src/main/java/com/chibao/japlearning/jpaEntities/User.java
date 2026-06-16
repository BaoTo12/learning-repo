package com.chibao.japlearning.jpaEntities;

import jakarta.persistence.*;
import org.apache.juli.logging.Log;
import org.apache.juli.logging.LogFactory;
import org.hibernate.annotations.ColumnDefault;

@Entity
@EntityListeners(AuditTrailListener.class)
public class User {
    private static Log log = LogFactory.getLog(User.class);

    @Id
    @GeneratedValue
    private int id;

    private String userName;
    @Column(columnDefinition = "varchar(255) default 'John Snow'")
    @ColumnDefault("John Snow")
    private String name;

    @Column(columnDefinition = "integer default 25")
    private Integer age;

    @Column(columnDefinition = "boolean default false")
    private Boolean locked;
    @Transient
    private String fullName;

    // Standard getters/setters
    @PrePersist
    public void logNewUserAttempt() {
        log.info("Attempting to add new user with username: " + userName);
    }

    @PostPersist
    public void logNewUserAdded() {
        log.info("Added user '" + userName + "' with ID: " + id);
    }

    @PreRemove
    public void logUserRemovalAttempt() {
        log.info("Attempting to delete user: " + userName);
    }

    @PostRemove
    public void logUserRemoval() {
        log.info("Deleted user: " + userName);
    }

    @PreUpdate
    public void logUserUpdateAttempt() {
        log.info("Attempting to update user: " + userName);
    }

    @PostUpdate
    public void logUserUpdate() {
        log.info("Updated user: " + userName);
    }


    public static Log getLog() {
        return log;
    }

    public static void setLog(Log log) {
        User.log = log;
    }

    public int getId() {
        return id;
    }

    public void setId(int id) {
        this.id = id;
    }

    public String getUserName() {
        return userName;
    }

    public void setUserName(String userName) {
        this.userName = userName;
    }


    public String getFullName() {
        return fullName;
    }

    public void setFullName(String fullName) {
        this.fullName = fullName;
    }
}