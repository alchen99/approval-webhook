from __future__ import print_function

import re

from wsgiref.simple_server import make_server
from pyramid.config import Configurator
from pyramid.view import view_config, view_defaults
from pyramid.response import Response
from github import Github

ENDPOINT = "webhook"

@view_defaults(
    route_name=ENDPOINT, renderer="json", request_method="POST"
)
class PayloadView(object):
    """
    View receiving of Github payload. By default, this view it's fired only if
    the request is json and method POST.
    """

    def __init__(self, request):
        self.request = request
        # Payload from Github, it's a dict
        self.payload = self.request.json
        with open('/etc/github/oauth', 'r') as file:
            self.github = Github(file.read().replace('\n', ''))

    @view_config(header="X-Github-Event:push")
    def payload_push(self):
        """This method is a continuation of PayloadView process, triggered if
        header HTTP-X-Github-Event type is Push"""
        print("No. commits in push:", len(self.payload['commits']))
        return Response("success")

    @view_config(header="X-Github-Event:pull_request_review")
    @view_config(header="X-Github-Event:pull_request")
    def payload_pull_request(self):
        """This method is a continuation of PayloadView process, triggered if
        header HTTP-X-Github-Event type is Pull Request"""
        print("PR", self.payload['action'])
        print("No. Commits in PR:", self.payload['pull_request']['commits'])
        return Response("success")

    @view_config(header="X-Github-Event:issue_comment")
    def payload_issue_comment(self):
        """This method is a continuation of PayloadView process, triggered if
        header HTTP-X-Github-Event type is Issue Comment"""

        # define GitHub repo and PR
        repo = self.github.get_repo(self.payload['repository']['owner']['login'] + '/' + self.payload['repository']['name'])
        pr = repo.get_pull(self.payload['issue']['number'])

        print("Issue Comment", self.payload['action'])

        """Check for comment with 2nd Approval. If not found then check number of approvers."""
        if re.search('2nd Approval', self.payload['comment']['body']) is None:
            num_approvers = len(re.findall('title=\"Approved\">(infa-\w+)<', self.payload['comment']['body']))
            if num_approvers == 0:
                print("PR has no approvers")
            elif num_approvers == 1:
                new_comment = re.sub('This PR is .*', 'This PR needs **2nd Approval**', self.payload['comment']['body'])
                pr.create_issue_comment(new_comment)
                print("PR needs second approver")
            elif num_approvers >= 2:
                labels = [label['name'] for label in self.payload['issue']['labels']]
                if "needs-2-approvals" in labels:
                    pr.remove_from_labels('needs-2-approvals')
                    pr.add_to_labels('approved2')
                    print("Removed label needs-2-approvals from PR!")

        return Response("success")

    @view_config(header="X-Github-Event:ping")
    def payload_ping(self):
        print("Pinged! Webhook created with id {}!".format(self.payload["hook"]["id"]))
        return {"status": 200}

    @view_config()
    def payload_else(self):
        print("ERROR: Unknown event! \n", self.request)
        return {"status": 500}


if __name__ == "__main__":
    config = Configurator()
    config.add_route(ENDPOINT, "/{}".format(ENDPOINT))
    config.scan()

    app = config.make_wsgi_app()
    server = make_server("0.0.0.0", 8080, app)
    server.serve_forever()
