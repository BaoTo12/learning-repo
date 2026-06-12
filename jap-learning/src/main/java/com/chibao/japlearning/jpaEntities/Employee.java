package com.chibao.japlearning.jpaEntities;

import jakarta.persistence.*;

@Entity
@Table(
        name = "employees",
        uniqueConstraints = {
                @UniqueConstraint(
                        name = "uk_employees_org_username",
                        columnNames = {"organization_id", "username"}
                )
        }
)
public class Employee {

    @Id
    private String id;

    @Column(name = "organization_id")
    private String organizationId;

    private String username;
}
