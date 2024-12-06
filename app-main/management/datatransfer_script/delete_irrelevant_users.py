import time
from publications.models import FileObject, Keyword, Person, Publication, Topic, Feature


def run():
    
    # get all users
    users = Person.objects.all()

    # Print in green text "Deleting irrelevant users"
    print("\033[92m" + "Deleting irrelevant users" + "\033[0m")
    # sleep for 1 second
    time.sleep(1)

    # loop through users
    for user in users:
        # Filter authored publications by this user 
        authored_publications = Publication.objects.filter(authors=user)
        
        # Filter edited publications by this user
        edited_publications = Publication.objects.filter(editors=user)

        # Filter supervised publications by this user
        supervised_publications = Publication.objects.filter(supervisors=user)

        if authored_publications.count() == 0 and edited_publications.count() == 0 and supervised_publications.count() == 0:
            print("Deleting user " + user.first)
            user.delete()


if __name__ == '__main__':
    run()
