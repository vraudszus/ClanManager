package com.playerranking.server.model.settings;

import jakarta.persistence.Embeddable;

@Embeddable
class DonationSettings {
  private boolean relativeDonation;
  private float donationFactor;
}
