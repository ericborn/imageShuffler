# -*- coding: utf-8 -*-
"""
Created on Fri Aug 21 17:29:05 2026

@author: eric
"""
import random

state_list = ['dirty','clean','faded','see through','latex','crisp']
state_list2 = ['shredded','tattered','torn','ripped']

thing_list = ['U.S. Army','U.S. Navy','U.S. Airforce','U.S. Marine','military','camouflage','fatigues']
thing_list2 = ['coveralls','overalls', 'work shirt', 'work pants',
               'work trousers', 'work shorts', 'flannel shirt', 'work jacket']
thing_list3 = ['bondage','bdsm','viking','western','witch','pirate', 'nun',
               'nurse','medieval','maid','doctor','bikini','babydoll',
               'lingerie','fishnet','bodysuit','bustier','corset']

show_list = ['sexy','skimpy','slutty','revealing','exposed','half on','tight']

cut_list = ['']

bikini_list = ['slingshot', 'string', 'micro', 'pearl', 'rope', 'thong', 'g-string']

modifier_list = ['cosplay','uniform','outfit','armor', 'fur', 'leather']

for i in range(0, 100):
    state_choice1 =''
    state_choice2 =''
    thing_choice = ''
    show_choice = ''
    cut_choice = ''
    modifier_choice = ''
    
    rand_state_choice = random.randint(0, 3)
    if (rand_state_choice == 1):
        state_choice1 = random.choice(state_list)
    elif (rand_state_choice == 2):
        state_choice2 = random.choice(state_list2)
    elif (rand_state_choice == 3):
        state_choice1 = random.choice(state_list)
        state_choice2 = random.choice(state_list2)
    
    rand_thing_choice = random.randint(0, 2)
    if (rand_thing_choice == 0):
        thing_choice = random.choice(thing_list)
    elif (rand_thing_choice == 1):
        thing_choice = random.choice(thing_list2)
    else:
        thing_choice = random.choice(thing_list3)
        
    if (thing_choice == 'bikini'):
        rand_extra_thing_choice = random.choice(bikini_list)
        thing_choice = rand_extra_thing_choice + ' ' + thing_choice
    
    rand_show_choice = random.randint(0, 1)
    if (rand_show_choice == 1):
        show_choice = random.choice(show_list)
    
    rand_cut_choice = random.randint(0, 1)
    if (rand_cut_choice == 1):
        cut_choice = random.choice(cut_list)
     
    modifier_choice = random.choice(modifier_list)
    # rand_modifier_choice = random.randint(0, 1)
    # if (rand_modifier_choice == 1):
    #     modifier_choice = random.choice(modifier_list)
        
    # print(str(rand_state_choice) + ' ' + str(rand_thing_choice) + ' ' + 
    #       str(rand_cut_choice) + ' ' + str(rand_modifier_choice))
    print(state_choice1 + ' ' + state_choice2 + ' ' + show_choice + ' ' +
           thing_choice  + ' ' + cut_choice + ' ' + modifier_choice)