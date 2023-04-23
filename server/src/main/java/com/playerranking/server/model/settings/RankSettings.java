package com.playerranking.server.model.settings;

import jakarta.persistence.Embeddable;

@Embeddable
class RankSettings {
  // member: 0, elder: 0.5, coLeader/leader: 1
  private float rank_factor;

  public float getRank_factor() {
    return rank_factor;
  }

  public void setRank_factor(float factor) {
    this.rank_factor = factor;
  }
}
