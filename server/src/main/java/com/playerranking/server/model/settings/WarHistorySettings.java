package com.playerranking.server.model.settings;

import jakarta.persistence.Embeddable;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;

@Embeddable class WarHistorySettings {
  private float emptyHistoryFactor;
  private boolean relativeWarHistory;
  private float warHistoryFactor;
  @Enumerated(EnumType.STRING)
  private IncompleteDataStrategy emptyHistoryStrategy;

  public float getEmptyHistoryFactor() {
    return emptyHistoryFactor;
  }

  public void setEmptyHistoryFactor(float emptyHistoryFactor) {
    this.emptyHistoryFactor = emptyHistoryFactor;
  }

  public IncompleteDataStrategy getEmptyHistoryStrategy() {
    return emptyHistoryStrategy;
  }
  public void setEmptyHistoryStrategy(IncompleteDataStrategy emptyHistoryStrategy) {
    this.emptyHistoryStrategy = emptyHistoryStrategy;
  }
}
