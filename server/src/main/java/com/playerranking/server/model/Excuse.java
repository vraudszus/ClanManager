package com.playerranking.server.model;

import com.playerranking.server.model.settings.RankingSettings;
import jakarta.persistence.*;

@Entity
public class Excuse {
  @Id @GeneratedValue
  private long id;
  @ManyToOne
  private RankingSettings rankingSettings;
  @ManyToOne
  private Player player;
  @Enumerated(EnumType.STRING)
  private ExcuseType type;

  enum ExcuseType {
    ONLY_ONE_DAY,
    ONLY_TWO_DAYS,
    ONLY_THREE_DAYS,
    PERSONAL_EXCUSE;
  }
}
