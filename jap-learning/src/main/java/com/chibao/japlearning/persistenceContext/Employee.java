package com.chibao.japlearning.persistenceContext;

import jakarta.persistence.*;

import java.util.List;

@Entity
public class Employee {
    @Id
    private int id;
    private String name;
    @ElementCollection
    @CollectionTable(name = "employee_phone", joinColumns = @JoinColumn(name = "employee_id"))
    private List<Phone> phones;

    // standard constructors, getters, and setters


    public Employee(int id, String name, List<Phone> phones) {
        this.id = id;
        this.name = name;
        this.phones = phones;
    }

    public int getId() {
        return id;
    }

    public void setId(int id) {
        this.id = id;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public List<Phone> getPhones() {
        return phones;
    }

    public void setPhones(List<Phone> phones) {
        this.phones = phones;
    }
}