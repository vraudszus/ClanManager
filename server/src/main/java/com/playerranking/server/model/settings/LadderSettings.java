package com.playerranking.server.model.settings;

import jakarta.persistence.Embeddable;

@Embeddable class LadderSettings {
  private float ladderFactor;

  public float getLadderFactor() {
    return ladderFactor;
  }

  public void setLadderFactor(float factor) {
    this.ladderFactor = factor;
  }
}
