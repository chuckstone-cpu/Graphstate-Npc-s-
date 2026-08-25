(define (domain two-tier)
  (:requirements :typing :negative-preconditions)
  
  (:types 
    location item door
  )

  (:predicates 
    (at-player ?loc - location)
    (at-item ?i - item ?loc - location)
    (has-item ?i - item)
    (connected ?l1 - location ?l2 - location)
    (door-at ?d - door ?loc - location)
    (locked ?d - door)
  )

  ;; The move action assumes the player is passing through a door to leave the location.
  ;; For standard STRIPS/pyperplan compatibility without ADL/exists, we explicitly parameterize the door.
  (:action move
    :parameters (?from - location ?to - location ?d - door)
    :precondition (and 
      (at-player ?from)
      (connected ?from ?to)
      (door-at ?d ?from)
      (not (locked ?d))
    )
    :effect (and 
      (not (at-player ?from))
      (at-player ?to)
    )
  )

  (:action pick_up
    :parameters (?i - item ?loc - location)
    :precondition (and 
      (at-player ?loc)
      (at-item ?i ?loc)
    )
    :effect (and 
      (not (at-item ?i ?loc))
      (has-item ?i)
    )
  )

  (:action unlock
    :parameters (?loc - location ?d - door ?k - item)
    :precondition (and 
      (at-player ?loc)
      (door-at ?d ?loc)
      (has-item ?k)
      (locked ?d)
    )
    :effect (and 
      (not (locked ?d))
    )
  )
)
