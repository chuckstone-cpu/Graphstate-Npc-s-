## Ontology of the castle (Unit 4: categories and objects).
## Every item belongs to a category, and the rules work on CATEGORIES rather
## than individual items:
##
##   Item
##   |-- Weapon
##   |   |-- LightWeapon : dagger
##   |   |-- HeavyWeapon : axe, hammer
##   |-- Potion          (usable only by the Warrior class - "the ways of a warrior")
##       |-- mana_potion, health_potion
##
##   Obstacle
##   |-- Barrel          (any Weapon smashes it)
##   |-- Door            (a locked Door needs a HeavyWeapon)
##   |-- CrackedWall     (only a hammer breaks it)
extends RefCounted

const PARENT := {
	"dagger": "LightWeapon", "axe": "HeavyWeapon", "hammer": "HeavyWeapon",
	"LightWeapon": "Weapon", "HeavyWeapon": "Weapon", "Weapon": "Item",
	"mana_potion": "Potion", "health_potion": "Potion", "Potion": "Item",
}

## Combat stats per weapon: damage per hit, seconds between hits.
const WEAPON_STATS := {
	"dagger": {"damage": 9.0, "cooldown": 0.55, "power": 1.0},
	"axe": {"damage": 16.0, "cooldown": 1.0, "power": 1.6},
	"hammer": {"damage": 20.0, "cooldown": 1.3, "power": 1.7},
}

## Seconds needed to smash an obstacle.
const SMASH_TIME := {"barrel": 0.7, "door": 2.5, "cracked": 3.0}

## is_a(x, C): is x in category C? Walks up the hierarchy (inheritance).
static func is_a(item: String, category: String) -> bool:
	var cur := item
	while cur != "":
		if cur == category:
			return true
		cur = PARENT.get(cur, "")
	return false

## Can an agent of this class use the item at all?
static func can_use(agent_class: String, item: String) -> bool:
	if is_a(item, "Potion"):
		return agent_class == "Warrior"
	if is_a(item, "Weapon"):
		return agent_class == "Rogue"      # the knight fights only with his sword
	return false

## Can this weapon smash this kind of obstacle?
static func can_smash(weapon: String, obstacle: String) -> bool:
	if weapon == "":
		return false
	match obstacle:
		"barrel": return is_a(weapon, "Weapon")
		"door": return is_a(weapon, "HeavyWeapon")
		"cracked": return weapon == "hammer"
	return false
