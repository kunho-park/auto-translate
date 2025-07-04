// priority: 100
StartupEvents.registry("block", (event) => {
    event.create("ftb:portal_holder")
        .parentModel("minecraft:block/reinforced_deepslate")
        .displayName("차원문 홀더")
        .unbreakable();
});
