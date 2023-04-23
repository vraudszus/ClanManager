package com.playerranking.server.model.settings;

import jakarta.persistence.*;

@Entity
public class RankingSettings {

  @Id private String id;

  @Column(nullable = false)
  private String writeSecret;

  @Column(nullable = false)
  private String clanTag;

  @Embedded
  private LadderSettings ladderSettings;
  @Embedded private WarHistorySettings warHistorySettings;
  @Embedded private CurrentWarSettings currentWarSettings;
  @Embedded private DonationSettings donationSettings;
  @Embedded private LoyaltySettings loyaltySettings;
  @Embedded private RankSettings rankSettings;
  @Embedded private InactivitySettings inactivitySettings;
  @Embedded private ExcuseSettings excuseSettings;
}
