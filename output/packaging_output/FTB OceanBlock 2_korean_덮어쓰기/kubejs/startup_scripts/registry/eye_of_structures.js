/* 
  custom eye of ender implementation allowing to find different structures
  authored by EnigmaQuip

  will locate the nearest structure that has the structure tag set
*/

const $EyeofEnder = Java.loadClass(
  "net.minecraft.world.entity.projectile.EyeOfEnder"
);
const $Registry = Java.loadClass("net.minecraft.core.registries.Registries");
const $TagKey = Java.loadClass("net.minecraft.tags.TagKey");

StartupEvents.registry("item", (event) => {
  //Custom Ender Eye
  event
    .create("ftb:nautical_eye")
    .displayName("항해의 눈")
    .unstackable()
    .use((level, player, interactionHand) => global.useNauticEye(level, player, interactionHand));


    //Custom Ender Eye
  event
  .create("ftb:ancient_eye")
  .displayName("고대의 눈")
  .unstackable()
  .use((level, player, interactionHand) => {
    let item = player.getHeldItem(interactionHand);
    player.startUsingItem(interactionHand);
    if (!level.clientSide) {
      let structureTag = $TagKey.create(
        $Registry.STRUCTURE,
        "minecraft:ancient_city"
      );

      let foundPos = level.findNearestMapStructure(
        structureTag,
        player.blockPosition(),
        1000,
        false
      );

      if (foundPos) {
        let eye = new $EyeofEnder(
          level,
          player.getX(),
          player.getY(0.5),
          player.getZ()
        );

        eye.setItem(item);
        eye.signalTo(foundPos);
        eye.spawn();

        level.playSound(
          null,
          player.getX(),
          player.getY(),
          player.getZ(),
          "entity.ender_eye.launch",
          player.getSoundSource(),
          0.5,
          0.5
        );

        player.swing(interactionHand);
        return true;
      }
    }
    return false;
  });
});


global.useNauticEye = (level, player, interactionHand) => {
  let item = player.getHeldItem(interactionHand);
  player.startUsingItem(interactionHand);

  try{
    if (!level.clientSide) {
      let structureTag = $TagKey.create(
        $Registry.STRUCTURE,
        "ftb:oceanlegendlocator"
      );
      console.log(structureTag);
      let foundPos = level.findNearestMapStructure(
        structureTag,
        player.blockPosition(),
        1000,
        false
      );
      if (foundPos) {
        let eye = new $EyeofEnder(
          level,
          player.getX(),
          player.getY(0.5),
          player.getZ()
        );
  
        eye.setItem(item);
        eye.signalTo(foundPos);
        eye.spawn();
  
        level.playSound(
          null,
          player.getX(),
          player.getY(),
          player.getZ(),
          "entity.ender_eye.launch",
          player.getSoundSource(),
          0.5,
          0.5
        );
  
        player.swing(interactionHand);
        return true;
      }
    }
    return false;
  }catch(e){
    console.error(e);
    return false;
  }
}