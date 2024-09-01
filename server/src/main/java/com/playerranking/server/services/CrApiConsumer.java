package com.playerranking.server.services;

import com.playerranking.server.model.Clan;
import com.playerranking.server.model.ClanRepository;
import com.playerranking.server.model.PlayerRepository;
import java.io.IOException;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.List;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.core.io.ClassPathResource;
import org.springframework.core.io.Resource;
import org.springframework.http.*;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

@Service
public class CrApiConsumer {
  private static final Logger logger = LoggerFactory.getLogger(CrApiConsumer.class);
  private static final String API_URL = "https://proxy.royaleapi.dev/v1";
  private static final String API_KEY;

  private final ClanRepository clanRepository;
  private final PlayerRepository playerRepository;
  private List<String> clanTags = Arrays.asList("GP9GRQ");

  static {
    Resource resource = new ClassPathResource("cr-api-token.txt");
    try {
      API_KEY = new String(resource.getInputStream().readAllBytes(), StandardCharsets.UTF_8);
    } catch (IOException e) {
      logger.error("Failed to read api token from file.");
      throw new RuntimeException(e);
    }
  }

  @Autowired
  public CrApiConsumer(ClanRepository clanRepository, PlayerRepository playerRepository) {
    this.clanRepository = clanRepository;
    this.playerRepository = playerRepository;
  }

  @Scheduled(fixedRate = 5000)
  public void updatePlayers() {
    for (String clanTag : clanTags) {
      updatePlayersOfClan(clanTag);
    }
  }

  private void updatePlayersOfClan(String clanTag) {
    RestTemplate restTemplate = new RestTemplate();

    ResponseEntity<Clan> response =
        restTemplate.exchange(
            getClanUri(clanTag), HttpMethod.GET, buildRequestEntity(), Clan.class);

    Clan clan = response.getBody();
    playerRepository.saveAll(clan.getMembers());
    clanRepository.save(clan);
    logger.info("Updated clan #{} and its {} members.", clanTag, clan.getMemberCount());
  }

  private URI getClanUri(String clanTag) {
    return URI.create(API_URL + "/clans/%23" + clanTag);
  }

  private HttpEntity<String> buildRequestEntity() {
    HttpHeaders headers = new HttpHeaders();
    headers.setAccept(List.of(MediaType.APPLICATION_JSON));
    headers.set("authorization", String.format("Bearer %s", API_KEY));

    return new HttpEntity<>(headers);
  }
}
