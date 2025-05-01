*** Settings ***
Documentation     Test suite for automating the registration form at qa-practice.netlify.app
Library           SeleniumLibrary

*** Variables ***
${URL}           https://qa-practice.netlify.app/register
${BROWSER}       chrome

*** Test Cases ***
Valid User Registration
    [Documentation]    Test registration with valid user data
    [Tags]    registration    smoke
    Open Browser    ${URL}    ${BROWSER}
    Maximize Browser Window
    Wait Until Element Is Visible    id=firstName    timeout=10s
    Input Text    id=firstName    John
    Input Text    id=lastName    Doe
    Input Text    id=email    john.doe@example.com
    Input Password    id=password    SecurePass123!
    Click Element    xpath=//button[@type='submit']
    Wait Until Page Contains    Registration successful    timeout=10s
    Page Should Contain    Registration successful
    [Teardown]    Close Browser

*** Keywords ***
Registration Page Should Be Open
    Wait Until Element Is Visible    id=firstName    timeout=10s
    Page Should Contain Element    id=lastName
    Page Should Contain Element    id=email
    Page Should Contain Element    id=password 