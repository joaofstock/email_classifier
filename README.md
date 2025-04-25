# email_classifier
This project contains a flask app that uses openai api to classify emails into queues and perform sentiment analysis. 

This project is a small demonstration of an email classification system.

It uses IMAP & SMTP from Gmail (it's a simple setup free of charge)

You will need an open ai API to run, as this is the model who perform the translation, classification, summary and sentiment analysis. 

The flask generates the sql.db to store the analysis. 

Public dataset of customer complaints: https://www.consumerfinance.gov/data-research/consumer-complaints/
