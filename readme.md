# TODO list

### To do...
- [] implement feature view
- [] check data in database against old find-artek
- [] check model setup against old find-artek
- [] clean up code (remove commented code, newlines etc) [started]


### Completed
- [x] fix map view on report page (and limit features to those from the report)
- [x] fix author links, etc...
- [x] implement simple search from front page
- [x] implement individual person view
- [x] Fix null issue for person list!
- [x] implement persons api
- [x] implement persons view (list of all persons)
- [x] Ensure confidential and unvalidate entries are filtered out! (This happens in the api serializer)






### Other notes:

```python
import 
ldap_server = 'ldaps://win.dtu.dk'     # Your LDAP server address
user = 'BYG-Artek_AD_Read'             # Your AD read-only username
password = 'xxxxxxxxxxxxxxxxxxx'       # Replace with your AD password
search_base = 'dc=win,dc=dtu,dc=dk'    # Base DN for your domain
```

```python
search_filter = '(&(givenName=Thomas)(sn=I*))'
```

```python
# Connect to the LDAP server
try:
    # Set up the server with secure connection and detailed logging
    server = Server(ldap_server, get_info=ALL, use_ssl=True)
    conn = Connection(server, user=user, password=password, auto_bind=True)
    # Perform the search
    conn.search(
        search_base=search_base,
        search_filter=search_filter,
        search_scope=SUBTREE,
        attributes=['*']  # Retrieve all attributes
    )
    # Process the results
    if conn.entries:
        for entry in conn.entries:
            print(entry.displayName)  # Print all details about the found entry
    else:
        print("No entries found .")
    # Unbind the connection
    conn.unbind()
except Exception as e:
    print(f"An error occurred: {e}")
```
