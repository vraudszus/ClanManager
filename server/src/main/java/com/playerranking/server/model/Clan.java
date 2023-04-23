package com.playerranking.server.model;

import com.fasterxml.jackson.annotation.JsonProperty;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.OneToMany;
import java.util.List;

@Entity
public class Clan {
  @Id
  private String tag;
  private String name;
  @JsonProperty("members")
  private int memberCount;

  @JsonProperty("memberList")
  @OneToMany
  private List<Player> members;

  public String getTag() {
    return tag;
  }

  public String getName() {
    return name;
  }

  public int getMemberCount() {
    return memberCount;
  }

  public List<Player> getMembers() {
    return members;
  }
}
