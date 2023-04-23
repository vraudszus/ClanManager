package com.playerranking.server;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableScheduling
public class PlayerRankingServerApplication {

	public static void main(String[] args) {
		SpringApplication.run(PlayerRankingServerApplication.class, args);
	}

}
