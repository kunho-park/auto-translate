// priority: 100
StartupEvents.registry("item", (event) => {
  // Emergency Rations
  global.food.forEach((t) => {
    event
      .create(`ftb:food_canned_${t[0].toLowerCase()}_open`)
      .displayName(`비상 식량 (${t[1]} 맛)`)
      .tooltip(Text.translate("item.ftb.food_canned.tooltip"))
      .food((food) => {
        food.nutrition(4).saturation(0.4);
      });
  });

  //Pebbles
  global.pebbles.forEach((pebble) => {
    event.create("ftb:" + pebble.toLowerCase().replace(" ", "_") + "_pebbles").displayName(pebble + " Pebbles");
  });

  // Random Items
  event.create("ftb:kelp_goo").displayName("켈프 수지");
  event.create("ftb:stacked_netherite").displayName("네더라이트 스크랩 합금");
  event.create("ftb:barrel_smasher").displayName("통 파쇄기");
  event.create("ftb:reactant_dust").displayName("반응물 가루");
  event.create("ftb:sculk_seeds").displayName("스컬크 씨앗").rarity("epic").glow(true);
  event.create("ftb:abyssal_pearl").displayName("§5심연의 진주§f").tooltip(Text.translate("item.ftb.abyssal_pearl.tooltip"));
  // Remove as not needed ATM
  // event.create("ftb:kelp_plastic").displayName("켈프 플라스틱");

  //GPS
  event
    .create("ftb:gps")
    .displayName("배 통신 장치")
    .tooltip(Text.translate("item.ftb.gps.tooltip"))  
    .maxStackSize(1);

  //GPS
  event
    .create("ftb:gps_broken")
    .displayName("고장난 배 통신 장치")
    .tooltip(Text.translate("item.ftb.gps_broken.tooltip"))
    .maxStackSize(1);

  //Magma Droplet
  event.create("ftb:magma_droplet").displayName("마그마 물방울");

  //Abyssal shard
  event.create("ftb:abyssal_fragment").displayName("심연의 조각");

  //rift charge meter
  event
    .create("ftb:rift_charge_meter")
    .displayName("균열 충전 측정기")
    .tooltip(Text.translate("item.ftb.rift_charge_meter.tooltip"))
    .maxStackSize(1)
    .use((level, player, hand) => {
      try {
        global.showRiftCharge(player);
      } catch (e) {
        console.log(e);
      }
      return true;
    });

  event
    .create("ftb:heart_of_the_rift")
    .displayName("균열의 심장")
    .tooltip(Text.translate("item.ftb.heart_of_the_rift.tooltip"))
    .maxStackSize(1)
    .rarity("epic");

  event
    .create("ftb:rift_attenuation_crystal")
    .displayName("균열 감쇠 수정")
    .tooltip(Text.translate("item.ftb.rift_attenuation_crystal.tooltip"))
    .maxStackSize(4)
    .rarity("uncommon");
  event
    .create("ftb:enhanced_rift_attenuation_crystal")
    .displayName("강화된 균열 감쇠 결정")
    .tooltip(Text.translate("item.ftb.enhanced_rift_attenuation_crystal.tooltip"))
    .maxStackSize(4)
    .rarity("rare");
  event
    .create("ftb:ultimate_rift_attenuation_crystal")
    .displayName("궁극의 균열 감쇠 수정")
    .tooltip(Text.translate("item.ftb.ultimate_rift_attenuation_crystal.tooltip"))
    .maxStackSize(4)
    .rarity("epic");
  event.create("ftb:charged_prosperity_seed").displayName("충전된 번영 시드");
  event.create("ftb:charged_voidflame_seed").displayName("충전된 공허 화염 시드");
  event.create("ftb:empowered_rift_seed").displayName("강화된 균열 시드");
  event.create("ftb:blank_sherd").displayName("빈 파편");

  event.create('ftb:creative_portal_switcher')
    .displayName('크리에이티브 차원문 전환기')
    event.create('ftb:rift_charge').displayName("균열 충전").tooltip([Text.translate("item.ftb.rift_charge.tooltip")]);

  event.create('ftb:rift_weaver_disc').displayName(`심해 속`).jukeboxPlayable("ftb:rift_weaver_boss", true).rarity('epic');
  event.create('ftb:mystic_depths_disc').displayName(`신비로운 심해`).rarity("epic").jukeboxPlayable("ftb:mystic_depths", true);


  event.create("ftb:abyssal_archives_log1").displayName(`심연의 기록 보관소 - 로그 #001`).rarity("epic").jukeboxPlayable("ftb:abyssal_archives_log1", true).texture("minecraft:item/music_disc_5")
    event.create("ftb:abyssal_archives_log2").displayName(`심연의 기록 보관소 - 로그 #002`).rarity("epic").jukeboxPlayable("ftb:abyssal_archives_log2", true).texture("minecraft:item/music_disc_5");
    event.create("ftb:abyssal_archives_log3").displayName(`심연의 기록 보관소 - 로그 #003`).rarity("epic").jukeboxPlayable("ftb:abyssal_archives_log3", true).texture("minecraft:item/music_disc_5");
    event.create("ftb:abyssal_archives_log4").displayName(`심연의 기록 보관소 - 로그 #004`).rarity("epic").jukeboxPlayable("ftb:abyssal_archives_log4", true).texture("minecraft:item/music_disc_5");
    event.create("ftb:abyssal_archives_log5").displayName(`심연의 기록 보관소 - 로그 #005`).rarity("epic").jukeboxPlayable("ftb:abyssal_archives_log5", true).texture("minecraft:item/music_disc_5");
    event.create("ftb:abyssal_archives_log6").displayName(`심연의 기록 보관소 - 로그 #006`).rarity("epic").jukeboxPlayable("ftb:abyssal_archives_log6", true).texture("minecraft:item/music_disc_5");
    event.create("ftb:abyssal_archives_log7").displayName(`심연의 기록 보관소 - 로그 #007`).rarity("epic").jukeboxPlayable("ftb:abyssal_archives_log7", true).texture("minecraft:item/music_disc_5");
    event.create("ftb:abyssal_archives_log8").displayName(`심연의 기록 보관소 - 로그 #008`).rarity("epic").jukeboxPlayable("ftb:abyssal_archives_log8", true).texture("minecraft:item/music_disc_5");
    event.create("ftb:abyssal_archives_log9").displayName(`심연의 기록 보관소 - 로그 #009`).rarity("epic").jukeboxPlayable("ftb:abyssal_archives_log9", true).texture("minecraft:item/music_disc_5");
    event.create("ftb:abyssal_archives_log10").displayName(`심연의 기록 보관소 - 로그 #010`).rarity("epic").jukeboxPlayable("ftb:abyssal_archives_log10", true).texture("minecraft:item/music_disc_5");
    event.create("ftb:abyssal_archives_log11").displayName(`심연의 기록 보관소 - 로그 #011`).rarity("epic").jukeboxPlayable("ftb:abyssal_archives_log11", true).texture("minecraft:item/music_disc_5");
    event.create("ftb:abyssal_archives_log12").displayName(`심연의 기록 보관소 - 로그 #012`).rarity("epic").jukeboxPlayable("ftb:abyssal_archives_log12", true).texture("minecraft:item/music_disc_5");
    event.create("ftb:abyssal_archives_log13").displayName(`심연의 기록 보관소 - 로그 #013`).rarity("epic").jukeboxPlayable("ftb:abyssal_archives_log13", true).texture("minecraft:item/music_disc_5");
    event.create("ftb:abyssal_archives_log14").displayName(`심연의 기록 보관소 - 로그 #014`).rarity("epic").jukeboxPlayable("ftb:abyssal_archives_log14", true).texture("minecraft:item/music_disc_5");
    event.create("ftb:abyssal_archives_log15").displayName(`심연의 기록 보관소 - 로그 #015`).rarity("epic").jukeboxPlayable("ftb:abyssal_archives_log15", true).texture("minecraft:item/music_disc_5");
    event.create("ftb:abyssal_archives_log16").displayName(`심연의 기록 보관소 - 로그 #016`).rarity("epic").jukeboxPlayable("ftb:abyssal_archives_log16", true).texture("minecraft:item/music_disc_5");
    event.create("ftb:abyssal_archives_log17").displayName(`심연의 기록 보관소 - 로그 #017`).rarity("epic").jukeboxPlayable("ftb:abyssal_archives_log17", true).texture("minecraft:item/music_disc_5");
    event.create("ftb:abyssal_archives_log18").displayName(`심연의 기록 보관소 - 로그 #018`).rarity("epic").jukeboxPlayable("ftb:abyssal_archives_log18", true).texture("minecraft:item/music_disc_5");
    event.create("ftb:abyssal_archives_thankyou").displayName(`심연의 기록 보관소 - 감사합니다`).rarity("epic").jukeboxPlayable("ftb:abyssal_archives_thankyou", true).texture("minecraft:item/music_disc_5");
  
});
