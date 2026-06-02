package com.chibao.edu.adapter.out.persistence;

import jakarta.persistence.*;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.time.LocalDateTime;

@Entity
@Table(name = "activity")
@Getter
@Setter
@AllArgsConstructor
@NoArgsConstructor
public class ActivityJpaEntity {

    @Id
    @GeneratedValue
    private Long id;

    @Column
    private LocalDateTime timestamp;

    @Column
    private long ownerAccountId;

    @Column
    private long sourceAccountId;

    @Column
    private long targetAccountId;

    @Column
    private long amount;

}