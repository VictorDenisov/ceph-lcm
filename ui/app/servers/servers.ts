import { Component } from '@angular/core';
import { DataService } from '../services/data';
import { Server } from '../models';

import * as _ from 'lodash';

@Component({
  templateUrl: './app/templates/servers.html',
})
export class ServersComponent {
  servers: Server[] = null;
  shownServerId: string = null;
  configuration: string[][] = [
    ['name', 'fqdn', 'ip'], ['state', 'cluster_id']
  ];

  constructor(private data: DataService) {
    this.fetchData();
  }

  fetchData() {
    this.data.server().findAll({})
      .then((servers: Server[]) => this.servers = servers);
  }

  showVersions(server: Server) {
    this.shownServerId = this.shownServerId === server.id ?
      null : server.id;
  }
}