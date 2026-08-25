(define (problem grid-problem)
  (:domain two-tier)
  
  (:objects 
    loc_spawn loc_pot loc_chest - location
    key chest - item
    door_1 door_2 - door
  )
  
  (:init
    ;; Player starts at spawn
    (at-player loc_spawn)
    
    ;; Items initial locations
    (at-item key loc_pot)
    (at-item chest loc_chest)
    
    ;; Connectivity mapping
    (connected loc_spawn loc_pot)
    (connected loc_pot loc_chest)
    
    ;; To move cleanly using our STRIPS-compatible `move` action, 
    ;; each departure point needs an associated door.
    
    ;; We map a dummy "open" door to the spawn to allow the player 
    ;; to move from loc_spawn to loc_pot freely.
    (door-at door_1 loc_spawn)
    
    ;; Door 2 is placed at the pot location to block movement to the chest
    (door-at door_2 loc_pot)
    (locked door_2)
  )
  
  (:goal
    (has-item chest)
  )
)
