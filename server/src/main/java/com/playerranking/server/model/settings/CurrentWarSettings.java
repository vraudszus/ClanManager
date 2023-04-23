package com.playerranking.server.model.settings;

import jakarta.persistence.Embeddable;

@Embeddable
class CurrentWarSettings {

  private boolean countIncompleteWeek;
  private boolean interpolateToFullWeek;
  private boolean relativeCurrentWar;
  private float currentWarFactor;

  private boolean linearFactorGrowth;
  public boolean isCountIncompleteWeek() {
    return countIncompleteWeek;
  }

  public void setCountIncompleteWeek(boolean countIncompleteWeek) {
    this.countIncompleteWeek = countIncompleteWeek;
  }

  public boolean isInterpolateToFullWeek() {
    return interpolateToFullWeek;
  }

  public void setInterpolateToFullWeek(boolean interpolateToFullWeek) {
    this.interpolateToFullWeek = interpolateToFullWeek;
  }

  public boolean isLinearFactorGrowth() {
    return linearFactorGrowth;
  }

  public void setLinearFactorGrowth(boolean linearFactorGrowth) {
    this.linearFactorGrowth = linearFactorGrowth;
  }
}
