package com.playerranking.server.model.settings;

import jakarta.persistence.Embeddable;

@Embeddable class LoyaltySettings {
  private int cappedAfterMonths;
  private boolean relativeLoyalty;
  private float loyaltyFactor;
}
