// const $KubeFluidType = Java.loadClass("dev.latvian.mods.kubejs.fluid.FluidTypeBuilder")
StartupEvents.registry("fluid", (event) => {

    event.create('ftb:molten_cast_iron')
    .displayName("녹은 주철")        
    .stillTexture("ftb:fluid/cast_iron_still")          
    .flowingTexture("ftb:fluid/cast_iron_flow")          
    .noBucket()
    .noBlock()
    .tint(0xafb4bf)
    event.create('ftb:molten_copper_alloy')
    .displayName("녹은 구리 합금")        
    .stillTexture("ftb:fluid/cast_iron_still")          
    .flowingTexture("ftb:fluid/cast_iron_flow")          
    .noBucket()
    .noBlock()
    .tint(0xcb673a)

});