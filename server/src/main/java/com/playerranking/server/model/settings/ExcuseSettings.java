package com.playerranking.server.model.settings;

import jakarta.persistence.Embeddable;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;

@Embeddable class ExcuseSettings {
  private float excusedWarFactor;
  @Enumerated(EnumType.STRING)
  private IncompleteDataStrategy excusedWarPolicy;
  @Enumerated(EnumType.STRING)
  private IncompleteWarPolicy incompleteWarPolicy;

  enum IncompleteWarPolicy {
    IGNORE,
    INTERPOLATE;
  }
}
