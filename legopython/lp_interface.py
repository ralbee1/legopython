'''A CLI interface for calling legopython functions.

To add a function to legopython UI, add an entry to support_functions_dict in support_functions_menu

Functions added to the legopython UI should follow the following formatting:
Parameter type hints are required for the interface to work. Docstrings are printed to console.

def functname(arg1:{vartype}, arg2:{vartype}, arg3:{vartype}) -> {responsetype}:
    """A short summary of the function

    arg1: arg1 description and usecase
    arg2: arg2 description and usecase
    arg3: arg3 description and usecase

    example) functname(arg1,arg2,arg3)
    """
'''
import ast
import time
import types
import typing
import subprocess
import sys
from legopython import lp_general, lp_settings
from legopython.lp_logging import logger


def list_function_parameters(function: str) -> dict:
    '''Get a list of parameters and typing hints from an explicit function.'''
    function_annotations = function.__annotations__
    if 'return' in function_annotations.keys():
        function_annotations.pop('return', None)
    return function_annotations


def prompt_user(question: str) -> str:
    '''Prompt a user and return a string. Allow exiting if they type it.'''
    user_input = input(question)
    if user_input.lower() in ('exit','quit',"'quit'","'exit'",'"exit"','"quit"'):
        print('f\n {user_input} detected, Exiting')
        sys.exit()
    return user_input


def prompt_set_setting():
    '''Prompt user to set a global variable'''
    settings = {
        1: {'name':'ENVIRONMENT', 'value': lp_settings.ENVIRONMENT},
        2: {'name':'LOGGER_LEVEL', 'value': lp_settings.LOGGER_LEVEL},
        3: {'name':'LOG_FILE_ENABLED', 'value': lp_settings.LOG_FILE_ENABLED},
        4: {'name':'LOG_LOCATION', 'value': lp_settings.LOG_LOCATION},
        5: {'name':'AWS_REGION', 'value': lp_settings.AWS_REGION}
    }

    #Print settings dict for user to choose from
    print('\n0. Return\n')
    for key, setting_name in settings.items():
        print(f'{key}: Current {setting_name["name"]} = {setting_name["value"]}')
    user_setting = lp_general.prompt_user_int('Enter # for setting to change: ', maximum=len(settings))

    if user_setting == 0:
        logger.info('Exiting without changing settings.')
        return support_functions_menu()

    #Prompt user setting - lowercase for standardization of user input
    lp_settings.set_global_setting(setting_name = settings[user_setting]['name'].lower(), new_value = prompt_user(f'Enter new value for {settings[user_setting]["name"]}: ').lower())


def prompt_user_string(parameter_name:str):
    '''Prompts user to enter string input, returns string'''
    user_input = prompt_user(f"Enter input for {parameter_name}: ")
    #If user chooses to enter nothing, skip.
    if user_input == '':
        return user_input
    
    #If user appended their own quotes, remove extra quotes.
    if user_input.startswith("'") and user_input.endswith("'"): #Remove ''
        user_input = user_input.replace("'","")
    if user_input.startswith('"') and user_input.endswith('"'): #Remove ""
        user_input = user_input.replace('"',"")
    return user_input


def prompt_user_bool(parameter_name:str):
    '''Prompts user to enter bool input as string, returns bool'''
    valid_input = False
    while valid_input is False:
        user_input = prompt_user(f"Enter true/false or y/n for {parameter_name}: ")
        #If user chooses to enter nothing, skip.
        if user_input == '':
            valid_input = True
        
        #If user appended their own quotes, remove extra quotes.
        if user_input.startswith("'") and user_input.endswith("'"): #Remove ''
            user_input = user_input.replace("'","")
        if user_input.startswith('"') and user_input.endswith('"'): #Remove ""
            user_input = user_input.replace('"',"")
        
        #Parse user string response to true or false.
        if user_input.lower() in ('y', 'true'):
            user_input = True
            valid_input = True
        elif user_input.lower() in ('n', 'false'):
            user_input = False
            valid_input = True
        elif valid_input is not True:
            print(f'Please enter true/false or y/n for {parameter_name}')
    return user_input


def prompt_user_int(parameter_name:str):
    '''Prompts user to enter int, returns int'''
    valid_input = False
    while valid_input is False:
        user_input = prompt_user(f'Enter whole number for {parameter_name}: ')
        #If user chooses to enter nothing, skip.
        if user_input == '':
            valid_input = True

        if user_input.isdigit():
            user_input = int(user_input)
            valid_input = True
        elif valid_input is not True:
            print(f'Please enter value for {parameter_name} in "7" or "100" format')
    return user_input


def prompt_user_list(parameter_name:str):
    '''Prompts user to enter list input, returns list'''
    valid_input = False
    while valid_input is False:
        user_input = prompt_user(f"Enter input for {parameter_name} as ['str','str'] or filename of a headerless 1 column CSV as 'excelfilename.csv': ")
        #If user chooses to enter nothing, skip.
        if user_input == '':
            valid_input = True

        #Parse user input with brackets as list and check for a provided csv.
        if user_input.startswith('[') and user_input.endswith(']'):
            user_input = ast.literal_eval(user_input)
            valid_input = True
        if user_input.endswith('.csv'):
            user_input = lp_general.read_1col_csv(user_input, hasheader = False)
            valid_input = True

        if valid_input is not True:
            print(f"Please enter value for {parameter_name} as list ['str','str'] or excelfilename.csv")
    return user_input


def prompt_user_dict(parameter_name:str):
    '''Prompts user to enter dict input, returns dict'''
    valid_input = False
    while valid_input is False:
        user_input = prompt_user(f'f"Enter input for parameter for {parameter_name} in dict format {"key": "value", "key": "value"}')
        #If user chooses to enter nothing, skip.
        if user_input == '':
            valid_input = True
        
        if user_input.startswith('{') and user_input.endswith('}'):
            user_input = ast.literal_eval(user_input)
            valid_input = True
        elif valid_input is not True:
            print(f'Please enter value for {parameter_name} in dict format {"key": "value", "key": "value"}')
    return user_input

def prompt_user_parameters(function_name:types.FunctionType, skip_params:list, prompt=True) -> dict:
    '''Prompt user for each parameter of {function_name} for use with support_functions_dict. 
    
    function name: Name of function, supports calling from other modules
    Allows skipping params in list of ints format. [int,int,int]
    '''
    parameter_dict = list_function_parameters(function_name)

    all_params_skipped = True
    for count, parameter in enumerate(parameter_dict):
        if count not in skip_params:
            all_params_skipped = False
    #skip asking for params if all parameters are skipped
    if all_params_skipped:
        return {}

    print('\n')
    help(function_name)
    parameter_input = {}
    print('(blank=skip // quit/exit returns to menu.)\n')
    for count, parameter in enumerate(parameter_dict):
        if count not in skip_params:

            #Prompt user for the type listed in the parameter's typehint.
            if parameter_dict[parameter] == type('string'):
                user_input = prompt_user_string(parameter)
            if parameter_dict[parameter] == type(False):
                user_input = prompt_user_bool(parameter_name=parameter)
            if parameter_dict[parameter] == type(7):
                user_input = prompt_user_int(parameter_name=parameter)
            if parameter_dict[parameter] == type(['str','str','str']):
                user_input = prompt_user_list(parameter_name=parameter)
            if parameter_dict[parameter] == type({"key": "value"}):
                user_input = prompt_user_dict(parameter_name=parameter)
            if parameter_dict[parameter] == typing.Union[list, str]:
                user_input = prompt_user_list(parameter_name=parameter)

            try: #If user entered blank, skip. Else, add to kwargs dictionary.
                if user_input != '':
                    parameter_input[parameter] = user_input
            except UnboundLocalError:
                print(f'{parameter_dict[parameter]} is not a supported type; Exiting.')
                time.sleep(3)
                return support_functions_menu()

    if prompt:
        print(f'\n {parameter_input} \n')
        if not lp_general.prompt_user_yesno(question=f"Are you sure you want to run {function_name.__name__} with the parameters above?"):
            return support_functions_menu()
    return parameter_input


def support_functions_menu():
    ''' Prints available functions and allows selection of function in support_functions_dict'''

    support_functions_dict = {
        0   : {'name':f'Change Settings    ENV:{lp_settings.ENVIRONMENT}','function':prompt_set_setting,'skip_param':[]},
        1   : {'name':'Update legopython: pip install','function':'pip install --upgrade legopython -i https://app.jfrog.io/artifactory/api/pypi/home-pypi/simple','skip_param':[]},
        2   : {'name':'Example Internal Application Module','function':'example_api_basic_auth','skip_param':[]}
    }

    #Display menu
    for key,value in support_functions_dict.items():
        if key == 0:
            print(f'\n{key}: {value["name"]}\n')
        else:
            print(f'{key}: {value["name"]}')
    print('\nCtrl + C or type exit to close.')

    user_input = lp_general.prompt_user_int('\nEnter the number for a Support Function ', maximum=(len(support_functions_dict)-1))

    #If user selected a function instead of a string, else call the string via command line.
    if isinstance(support_functions_dict[user_input]['function'], types.FunctionType):
        func = support_functions_dict[user_input]['function']
        skip_params = support_functions_dict[user_input]['skip_param']
        user_parameters = prompt_user_parameters(func, skip_params)
        if user_parameters == {}: #if no user parameters entered or if all parameters skip
            func()
        else:
            func(**user_parameters)

        print(f"\nCompleted running function {support_functions_dict[user_input]['function'].__name__}. Returning to main menu.")
    else:
        subprocess.call(support_functions_dict[user_input]['function'],shell=True)
        print(f"\nCompleted running function {support_functions_dict[user_input]['function']}. Returning to main menu.")

    time.sleep(3)
    return support_functions_menu()


def main():
    ''' Start the CLI interface loop'''
    support_functions_menu()

if __name__ == '__main__':
    main()
