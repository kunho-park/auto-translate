// Custom tooltips for items
ItemEvents.tooltip(tooltip => {
    // Add custom tooltips
    tooltip.add('minecraft:diamond', 'A precious gem that shines brightly')
    tooltip.add('minecraft:iron_ingot', 'Essential material for crafting')
    tooltip.add('minecraft:gold_ingot', 'Valuable metal with magical properties')

    // Add advanced tooltips
    tooltip.addAdvanced('minecraft:diamond_sword', (item, advanced, text) => {
        text.add(1, Text.of('Legendary weapon of heroes').color(0x55FF55))
        text.add(2, Text.of('Deals extra damage to monsters').color(0xFFFF55))
    })

    // Conditional tooltips
    tooltip.addAdvanced('minecraft:enchanted_book', (item, advanced, text) => {
        if (item.nbt && item.nbt.StoredEnchantments) {
            text.add(1, Text.of('Contains magical knowledge').color(0x9955FF))
        }
    })
})

// Custom item names
StartupEvents.registry('item', event => {
    event.create('custom_gem')
        .displayName('Mystical Crystal')
        .tooltip('A crystal infused with ancient magic')
        .rarity('epic')
})

// Chat messages
PlayerEvents.chat(event => {
    if (event.message === 'help') {
        event.player.tell('Welcome to the server! Type /spawn to get started')
        event.cancel()
    }

    if (event.message.startsWith('info')) {
        event.player.tell('Server Information: This is a magical adventure server')
        event.cancel()
    }
}) 