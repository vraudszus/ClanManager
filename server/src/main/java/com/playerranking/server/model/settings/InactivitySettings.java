package com.playerranking.server.model.settings;

import jakarta.persistence.Embeddable;

@Embeddable class InactivitySettings {
  private int inactivityAfterDays;
  private boolean relativeInactivity;
  private float inactivityFactor;

  public int getInactivityAfterDays() {
    return inactivityAfterDays;
  }

  public void setInactivityAfterDays(int inactivityAfterDays) {
    this.inactivityAfterDays = inactivityAfterDays;
  }
}
