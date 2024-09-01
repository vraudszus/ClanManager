package com.playerranking.server.model;

import com.fasterxml.jackson.annotation.JsonFormat;
import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.persistence.*;
import java.sql.Timestamp;

@Entity
public class Player {

  @Id
  private String tag;

  @Column(nullable = false)
  private String name;

  @Column(nullable = false)
  private int trophies;

  @JsonProperty("lastSeen")
  @JsonFormat(pattern = "yyyyMMdd'T'HHmmss.000'Z'")
  private Timestamp lastOnline;

  @Enumerated(EnumType.STRING)
  private Role role;

  private int donations;

  public String getTag() {
    return tag;
  }

  public String getName() {
    return name;
  }

  public int getTrophies() {
    return trophies;
  }

  public Timestamp getLastOnline() {
    return lastOnline;
  }

  public Role getRole() {
    return role;
  }

  public int getDonations() {
    return donations;
  }
}
